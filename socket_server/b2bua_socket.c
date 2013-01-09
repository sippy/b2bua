#define _WITH_DPRINTF 1

#include <sys/types.h>
#include <sys/uio.h>
#include <netinet/in.h>
#include <errno.h>
#include <poll.h>
#include <pthread.h>
#if defined(__FreeBSD__)
#include <pthread_np.h>
#endif
#include <resolv.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include "iksemel.h"

#include "b2bua_socket.h"
#include "ss_base64.h"
#include "ss_network.h"
#include "ss_lthread.h"
#include "ss_util.h"

struct b2bua_xchg_args {
    int socket;
    struct lthread_args *largs;
    pthread_mutex_t status_mutex;
    int status;
    struct b2bua_slot *bslots;
    /*
     * The variables below should only be accessed from the
     * worker (rx) thread.
     */
    struct queue *inpacket_queue;
    pthread_t tx_thread;
    /*
     * The variables below can be modified/accessed from the parent
     * thread only (b2bua_acceptor_run).
     */
    pthread_t rx_thread;
    struct b2bua_xchg_args *next;
    struct b2bua_xchg_args *prev;
};

#define B2BUA_XCHG_RUNS 0
#define B2BUA_XCHG_DEAD -1

#if !defined(INFTIM)
#define INFTIM (-1)
#endif

static void b2bua_xchg_tx(struct b2bua_xchg_args *);
static void b2bua_xchg_rx(struct b2bua_xchg_args *);

extern int pthread_timedjoin_np(pthread_t, void **,
  const struct timespec *);

struct b2bua_slot *
b2bua_getslot(struct b2bua_slot *bslots, str *call_id)
{
    struct b2bua_slot *bslot;
    int nslots, slotnum;
    int hash;

    nslots = 0;
    for (bslot = bslots; bslot != NULL; bslot = bslot->next) {
        nslots += 1;
    }
    hash = hash_string(call_id, 2);
    slotnum = hash % nslots;
    for (bslot = bslots; slotnum > 0; slotnum--) {
        bslot = bslot->next;
    }
    return bslot;
}

struct b2bua_slot *
b2bua_getslot_by_id(struct b2bua_slot *bslots, int id)
{
    struct b2bua_slot *bslot;

    for (bslot = bslots; bslot != NULL; bslot = bslot->next) {
        if (bslot->id == id)
            return bslot;
    }
    return NULL;
}

static int
b2bua_xchg_getstatus(struct b2bua_xchg_args *bargs)
{
    int status;

    pthread_mutex_lock(&bargs->status_mutex);
    status = bargs->status;
    pthread_mutex_unlock(&bargs->status_mutex);
    return status;
}

void
b2bua_acceptor_run(struct lthread_args *args)
{
    int n, s;
    socklen_t ralen;
    struct sockaddr_storage ia;
    struct b2bua_xchg_args *bargs_head, *bargs, *bargs1;
    char *cmd_listen_port;

    bargs_head = NULL;

    printf("b2bua_acceptor_run(%s)\n", args->cmd_listen_addr);
    asprintf(&cmd_listen_port, "%d", args->cmd_listen_port);
    n = resolve(sstosa(&ia), AF_INET, args->cmd_listen_addr, cmd_listen_port, AI_PASSIVE);
    free(cmd_listen_port);
    printf("resolve(%d)\n", n);

    s = socket(AF_INET, SOCK_STREAM, 0);
    printf("socket(%d)\n", s);
    setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &s, sizeof s);
    n = bind(s, sstosa(&ia), SS_LEN(&ia));
    printf("bind(%d)\n", n);
    n = listen(s, 32);
    for (;;) {
        for (bargs = bargs_head; bargs != NULL; bargs = bargs1) {
            bargs1 = bargs->next;
            if (b2bua_xchg_getstatus(bargs) != B2BUA_XCHG_RUNS) {
                printf("collecting dead xchg thread\n");
                pthread_join(bargs->rx_thread, NULL);
                if (bargs->prev != NULL)
                    bargs->prev->next = bargs->next;
                else
                    bargs_head = bargs->next;
                if (bargs->next != NULL)
                    bargs->next->prev = bargs->prev;
                free(bargs);
            }
        }
        ralen = sizeof(ia);
        n = accept(s, sstosa(&ia), &ralen);
        if (n < 0)
            continue;
        printf("accept(%d)\n", n);
        bargs = malloc(sizeof(*bargs));
        if (bargs == NULL) {
            fprintf(stderr, "b2bua_acceptor_run: no mem\n");
            close(n);
            continue;
        }
        memset(bargs, '\0', sizeof(*bargs));
        bargs->largs = args;
        bargs->socket = n;
        bargs->status = B2BUA_XCHG_RUNS;
        bargs->bslots = args->bslots;
        pthread_mutex_init(&(bargs->status_mutex), NULL);
        n = pthread_create(&bargs->rx_thread, NULL, (void *(*)(void *))&b2bua_xchg_rx, bargs);
        if (n != 0) {
            fprintf(stderr, "b2bua_acceptor_run: pthread_create() failed\n");
            close(n);
            free(bargs);
            continue;
        }
        if (bargs_head != NULL)
            bargs_head->prev = bargs;
        bargs->next = bargs_head;
        bargs->prev = NULL;
        bargs_head = bargs;
    }
}

static void
b2bua_xchg_setstatus(struct b2bua_xchg_args *bargs, int status)
{

    pthread_mutex_lock(&bargs->status_mutex);
    bargs->status = status;
    pthread_mutex_unlock(&bargs->status_mutex);
}

#define XMPP_PROLOGUE "<?xml version='1.0'?>\n <stream:stream>\n"

static void
b2bua_xchg_tx(struct b2bua_xchg_args *bargs)
{
    int i, buflen;
    struct wi *wi;
    char b64_databuf[11 * 1024];
    char *outbuf;

    send(bargs->socket, XMPP_PROLOGUE, sizeof(XMPP_PROLOGUE) - 1, MSG_NOSIGNAL);
    for (;;) {
        wi = queue_get_item(bargs->inpacket_queue, 1);
        if (wi == NULL) {
            if (b2bua_xchg_getstatus(bargs) != B2BUA_XCHG_RUNS) {
                return;
            }
            continue;
        }
#ifdef DEBUG
        printf("incoming size=%d, from=%s:%d, to=%s\n", INP(wi).rsize,
          INP(wi).remote_addr, INP(wi).remote_port, INP(wi).local_addr);
#endif

        i = ss_b64_ntop(INP(wi).databuf, INP(wi).rsize, b64_databuf, sizeof(b64_databuf));
        buflen = asprintf(&outbuf, "  <incoming_packet\n" \
          "   src_addr=\"%s\"\n" \
          "   src_port=\"%d\"\n" \
          "   dst_addr=\"%s\"\n" \
          "   dst_port=\"%d\"\n" \
          "   rtime=\"%f\"\n" \
          "   msg=\"%.*s\"\n" \
          "  />\n", INP(wi).remote_addr, INP(wi).remote_port, INP(wi).local_addr, INP(wi).local_port, \
          INP(wi).dtime, i, b64_databuf);
        i = send(bargs->socket, outbuf, buflen, MSG_NOSIGNAL);
        free(outbuf);
        if (i < 0) {
            if (b2bua_xchg_getstatus(bargs) == B2BUA_XCHG_RUNS) {
                b2bua_xchg_setstatus(bargs, B2BUA_XCHG_DEAD);
                shutdown(bargs->socket, SHUT_RDWR);
            }
            queue_put_item(wi, bargs->inpacket_queue);
            return;
        }
        wi_free(wi);
    }
}

struct wi *
wi_malloc(enum wi_type type)
{
    struct wi *wi;

    wi = malloc(sizeof(*wi));
    if (wi == NULL)
        return wi;
    memset(wi, '\0', sizeof(*wi));
    wi->wi_type = type;
    return wi;
}

void
wi_free(struct wi *wi)
{

    switch (wi->wi_type) {
    case WI_OUTPACKET:
        if (OUTP(wi).databuf != NULL)
            free(OUTP(wi).databuf);
        if (OUTP(wi).remote_addr != NULL)
            free(OUTP(wi).remote_addr);
        if (OUTP(wi).remote_port != NULL)
            free(OUTP(wi).remote_port);
        if (OUTP(wi).local_addr != NULL)
            free(OUTP(wi).local_addr);
        break;

    case WI_INPACKET:
        if (INP(wi).databuf != NULL)
            free(INP(wi).databuf);
        if (INP(wi).remote_addr != NULL)
            free(INP(wi).remote_addr);
        if (INP(wi).local_addr != NULL)
            free(INP(wi).local_addr);
        break;

    default:
        fprintf(stderr, "unknown wi_type: %d\n", wi->wi_type);
        abort();
    }
    free(wi);
}

static int
b2bua_xchg_in_stream(struct b2bua_xchg_args *bargs, int type, iks *node)
{
    iks *y;
    struct wi *wi;
    u_char b64_databuf[8 * 1024];
    int id, i;
    struct b2bua_slot *bslot;

    switch(type) {
    case IKS_NODE_START:
        break;

    case IKS_NODE_NORMAL:
        if (iks_type(node) == IKS_TAG && strcmp("outgoing_packet", iks_name(node)) == 0) {
#ifdef DEBUG
            printf ("Recvd : %s\n", iks_string(iks_stack(node), node));
#endif
            wi = wi_malloc(WI_OUTPACKET);
            if (wi == NULL) {
                iks_delete(node);
                return IKS_NOMEM;
            }
            y = iks_attrib(node);
            while (y) {
                if (strcmp("dst_addr", iks_name(y)) == 0) {
                    OUTP(wi).remote_addr = strdup(iks_cdata(y));
                } else if (strcmp("dst_port", iks_name(y)) == 0) {
                    OUTP(wi).remote_port = strdup(iks_cdata(y));
                } else if (strcmp("src_addr", iks_name(y)) == 0) {
                    OUTP(wi).local_addr = strdup(iks_cdata(y));
                } else if (strcmp("src_port", iks_name(y)) == 0) {
                    OUTP(wi).local_port = strtol(iks_cdata(y), (char **)NULL, 10);
                } else if (strcmp("msg", iks_name(y)) == 0) {
                    OUTP(wi).ssize = ss_b64_pton(iks_cdata(y), b64_databuf, sizeof(b64_databuf));
                    if (OUTP(wi).ssize <= 0) {
                        wi_free(wi);
                        iks_delete(node);
                        return IKS_BADXML;
                    }
                    OUTP(wi).databuf = malloc(OUTP(wi).ssize);
                    if (OUTP(wi).databuf == NULL) {
                        wi_free(wi);
                        iks_delete(node);
                        return IKS_NOMEM;
                    }
                    memcpy(OUTP(wi).databuf, b64_databuf, OUTP(wi).ssize);
                } else {
                    fprintf(stderr, "unknown attribute: %s='%s'\n", iks_name(y), iks_cdata(y));
                    wi_free(wi);
                    iks_delete(node);
                    return IKS_BADXML;
                }
                y = iks_next(y);
            }
            if (OUTP(wi).remote_addr == NULL) {
                fprintf(stderr, "'dst_addr' attribute is missing\n");
                wi_free(wi);
                iks_delete(node);
                return IKS_BADXML;
            }
            if (OUTP(wi).local_addr == NULL) {
                fprintf(stderr, "'src_addr' attribute is missing\n");
                wi_free(wi);
                iks_delete(node);
                return IKS_BADXML;
            }
            if (OUTP(wi).remote_port == NULL) {
                fprintf(stderr, "'dst_port' attribute is missing\n");
                wi_free(wi);
                iks_delete(node);
                return IKS_BADXML;
            }
            if (OUTP(wi).local_port <= 0) {
                fprintf(stderr, "'src_port' attribute is missing\n");
                wi_free(wi);
                iks_delete(node);
                return IKS_BADXML;
            }
            if (OUTP(wi).databuf == NULL) {
                fprintf(stderr, "'msg' attribute is missing\n");
                wi_free(wi);
                iks_delete(node);
                return IKS_BADXML;
            }
            queue_put_item(wi, &bargs->largs->outpacket_queue);
        } else if (iks_type(node) == IKS_TAG && strcmp("b2bua_slot", iks_name(node)) == 0) {
            if (bargs->inpacket_queue != NULL) {
                fprintf(stderr, "slot is already assigned\n");
                iks_delete(node);
                return IKS_OK;
            }
            y = iks_attrib(node);
            if (strcmp("id", iks_name(y)) != 0) {
                iks_delete(node);
                return IKS_BADXML;
            }
            id = strtol(iks_cdata(y), (char **)NULL, 10);
            bslot = b2bua_getslot_by_id(bargs->bslots, id);
            if (bslot == NULL) {
                 fprintf(stderr, "unknown slot id=%d\n", id);
                 iks_delete(node);
                 return IKS_OK;
            }
            bargs->inpacket_queue = &bslot->inpacket_queue;
            i = pthread_create(&bargs->tx_thread, NULL, (void *(*)(void *))&b2bua_xchg_tx, bargs);
            printf("fd %d associated with the slot %d\n", bargs->socket, id);
        }

        break;

    case IKS_NODE_STOP:
    default:
        break;
    }
    iks_delete(node);

    return IKS_OK;
}

static void
b2bua_xchg_rx(struct b2bua_xchg_args *bargs)
{
    int i;
    iksparser *p;
    enum iksneterror recv_stat;
    struct timespec tsp;

    p = iks_stream_new("b2bua:socket_server", (void *)bargs, (iksStreamHook *)b2bua_xchg_in_stream);
    i = iks_connect_fd(p, bargs->socket);
    printf("iks_connect_fd(%d)\n", i);

    for (;;) {
        recv_stat = iks_recv(p, -1);
        switch (recv_stat) {
        case IKS_NET_NODNS:
        case IKS_NET_NOSOCK:
        case IKS_NET_NOCONN:
        case IKS_NET_RWERR:
        case IKS_NET_NOTSUPP:
            printf("b2bua_xchg_rx: socket gone\n");
            if (b2bua_xchg_getstatus(bargs) == B2BUA_XCHG_RUNS) {
                b2bua_xchg_setstatus(bargs, B2BUA_XCHG_DEAD);
                shutdown(bargs->socket, SHUT_RDWR);
            }
            if (bargs->inpacket_queue != NULL) {
                for (;;) {
                    pthread_mutex_lock(&bargs->inpacket_queue->mutex);
                    pthread_cond_broadcast(&bargs->inpacket_queue->cond);
                    pthread_mutex_unlock(&bargs->inpacket_queue->mutex);
                    clock_gettime(CLOCK_REALTIME, &tsp);
                    tsp.tv_nsec += 10000000; /* 10ms */
                    if (pthread_timedjoin_np(bargs->tx_thread, NULL, &tsp) != ETIMEDOUT)
                        break;
                }
            }
            close(bargs->socket);
            printf("b2bua_xchg_rx: socket gone 1\n");
            return;

        default:
            break;
        }
    }
}
