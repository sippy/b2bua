#define _WITH_DPRINTF 1

#include <sys/types.h>
#include <sys/uio.h>
#include <netinet/in.h>
#include <errno.h>
#include <poll.h>
#include <pthread.h>
#include <resolv.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "iksemel.h"

#include "ss_network.h"
#include "ss_lthread.h"

struct b2bua_xchg_args {
    int socket;
    struct lthread_args *largs;
    pthread_mutex_t status_mutex;
    int status;
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

static void b2bua_xchg_tx(struct b2bua_xchg_args *);
static void b2bua_xchg_rx(struct b2bua_xchg_args *);

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
    int n, s, ralen;
    struct sockaddr_storage ia;
    struct b2bua_xchg_args *bargs_head, *bargs, *bargs1;

    bargs_head = NULL;

    printf("b2bua_acceptor_run(%s)\n", args->listen_addr);
    n = resolve(sstosa(&ia), AF_INET, args->listen_addr, "22223", AI_PASSIVE);
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
        bargs->largs = args;
        bargs->socket = n;
        bargs->status = B2BUA_XCHG_RUNS;
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

static void
b2bua_xchg_tx(struct b2bua_xchg_args *bargs)
{
    struct pollfd pfds[1];
    int i;
    struct wi *wi;
    char b64_databuf[8 * 1024];

    dprintf(bargs->socket, "<?xml version='1.0'?>\n <stream:stream>\n");
    pfds[0].fd = bargs->socket;
    for (;;) {
        for (;;) {
            pfds[0].events = POLLOUT;
            pfds[0].revents = 0;

            i = poll(pfds, 1, INFTIM);
            if (i == 0)
                continue;
            if (i < 0 && errno == EINTR)
                continue;
            if (i < 0 || pfds[0].revents & (POLLNVAL | POLLHUP)) {
                /*printf("b2bua_xchg_tx: socket gone\n");*/
                if (b2bua_xchg_getstatus(bargs) == B2BUA_XCHG_RUNS) {
                    b2bua_xchg_setstatus(bargs, B2BUA_XCHG_DEAD);
                    shutdown(bargs->socket, SHUT_RDWR);
                }
                return;
            }
            if ((pfds[0].revents & POLLOUT) != 0)
                break;
        }

        pthread_mutex_lock(&bargs->largs->inpacket_queue->mutex);
        while (bargs->largs->inpacket_queue->head == NULL) {
            pthread_cond_wait(&bargs->largs->inpacket_queue->cond,
              &bargs->largs->inpacket_queue->mutex);
            if (b2bua_xchg_getstatus(bargs) != B2BUA_XCHG_RUNS) {
                pthread_mutex_unlock(&bargs->largs->inpacket_queue->mutex);
                return;
            }
        }
        wi = bargs->largs->inpacket_queue->head;
        bargs->largs->inpacket_queue->head = wi->next;
        pthread_mutex_unlock(&bargs->largs->inpacket_queue->mutex);
        printf("incoming size=%d, from=%s:%d, to=%s\n", INP(wi).rsize,
          INP(wi).remote_addr, INP(wi).remote_port, INP(wi).local_addr);

        printf("b2bua_xchg_tx, POLLOUT\n");
        i = b64_ntop(INP(wi).databuf, INP(wi).rsize, b64_databuf, sizeof(b64_databuf));
        dprintf(bargs->socket, "  <incoming_packet\n" \
          "   src_addr=\"%s\"\n" \
          "   src_port=\"%d\"\n" \
          "   dst_addr=\"%s\"\n" \
          "   dst_port=\"%d\"\n" \
          "   rtime=\"%f\"\n" \
          "   msg=\"%.*s\"\n" \
          "  />\n", INP(wi).remote_addr, INP(wi).remote_port, INP(wi).local_addr, INP(wi).local_port, \
          INP(wi).dtime, i, b64_databuf);
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
    char b64_databuf[8 * 1024];

    switch(type) {
    case IKS_NODE_START:
        break;

    case IKS_NODE_NORMAL:
        if (iks_type(node) == IKS_TAG && strcmp("outgoing_packet", iks_name(node)) == 0) {
            printf ("Recvd : %s\n", iks_string(iks_stack(node), node));
            wi = wi_malloc(WI_OUTPACKET);
            if (wi == NULL)
                return IKS_NOMEM;
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
                    OUTP(wi).ssize = b64_pton(iks_cdata(y), b64_databuf, sizeof(b64_databuf));
                    if (OUTP(wi).ssize <= 0) {
                        wi_free(wi);
                        return IKS_BADXML;
                    }
                    OUTP(wi).databuf = malloc(OUTP(wi).ssize);
                    if (OUTP(wi).databuf == NULL) {
                        wi_free(wi);
                        return IKS_NOMEM;
                    }
                    memcpy(OUTP(wi).databuf, b64_databuf, OUTP(wi).ssize);
                } else {
                    fprintf(stderr, "unknown attribute: %s='%s'\n", iks_name(y), iks_cdata(y));
                    wi_free(wi);
                    return IKS_BADXML;
                }
                y = iks_next(y);
            }
            if (OUTP(wi).remote_addr == NULL) {
                fprintf(stderr, "'dst_addr' attribute is missing\n");
                wi_free(wi);
                return IKS_BADXML;
            }
            if (OUTP(wi).local_addr == NULL) {
                fprintf(stderr, "'src_addr' attribute is missing\n");
                wi_free(wi);
                return IKS_BADXML;
            }
            if (OUTP(wi).remote_port == NULL) {
                fprintf(stderr, "'dst_port' attribute is missing\n");
                wi_free(wi);
                return IKS_BADXML;
            }
            if (OUTP(wi).local_port <= 0) {
                fprintf(stderr, "'src_port' attribute is missing\n");
                wi_free(wi);
                return IKS_BADXML;
            }
            if (OUTP(wi).databuf == NULL) {
                fprintf(stderr, "'msg' attribute is missing\n");
                wi_free(wi);
                return IKS_BADXML;
            }
            queue_put_item(wi, &bargs->largs->outpacket_queue);
        }
        break;

    case IKS_NODE_STOP:
    default:
        break;
    }

    return IKS_OK;
}

static void
b2bua_xchg_rx(struct b2bua_xchg_args *bargs)
{
    int i;
    iksparser *p;
    enum iksneterror recv_stat;
    pthread_t tx_thread;

    p = iks_stream_new("b2bua:socket_server", (void *)bargs, (iksStreamHook *)b2bua_xchg_in_stream);
    i = iks_connect_fd(p, bargs->socket);
    printf("iks_connect_fd(%d)\n", i);

    i = pthread_create(&tx_thread, NULL, (void *(*)(void *))&b2bua_xchg_tx, bargs);

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
                pthread_mutex_lock(&bargs->largs->inpacket_queue->mutex);
                pthread_cond_broadcast(&bargs->largs->inpacket_queue->cond);
                pthread_mutex_unlock(&bargs->largs->inpacket_queue->mutex);
                shutdown(bargs->socket, SHUT_RDWR);
            }
            pthread_join(tx_thread, NULL);
            close(bargs->socket);
            printf("b2bua_xchg_rx: socket gone 1\n");
            return;

        default:
            break;
        }
    }
}
