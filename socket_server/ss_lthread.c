#include <ctype.h>
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "b2bua_socket.h"
#include "ss_lthread.h"
#include "ss_network.h"
#include "ss_util.h"

struct lthread
{
    struct lthread_args args;
    pthread_t rx_thread;
    struct lthread *next;
    int status;
};

#define LLTHREAD_RUNS 0
#define LLTHREAD_DEAD -1

static int lthread_sock_prepare(struct lthread_args *);
static void lthread_rx(struct lthread_args *args);
static void lthread_tx(struct lthread_args *args);

void
lthread_mgr_run(struct lthread_args *args)
{
    struct lthread *lthread_head, *lthread;
    struct wi *wi;
    int i;

    lthread = malloc(sizeof(*lthread));
    memset(lthread, '\0', sizeof(*lthread));
    if (lthread == NULL) {
        fprintf(stderr, "lthread_mgr_run: out of mem\n");
        exit(1);
    }
    lthread->args.listen_addr = args->listen_addr;
    lthread->args.listen_port = args->listen_port;
    if (lthread_sock_prepare(&lthread->args) != 0) {
        fprintf(stderr, "lthread_sock_prepare(%s:%d) = -1\n", args->listen_addr, args->listen_port);
        exit(1);
    }
    pthread_cond_init(&lthread->args.outpacket_queue.cond, NULL);
    pthread_mutex_init(&lthread->args.outpacket_queue.mutex, NULL);
    lthread->args.outpacket_queue.name = strdup("B2B->NET (wildcard)");
    lthread->args.wildcard = 1;
    lthread->args.bslots = args->bslots;

    i = pthread_create(&lthread->rx_thread, NULL, (void *(*)(void *))&lthread_rx, &lthread->args);
    printf("%d\n", i);
    lthread_head = lthread;
    for (;;) {
        wi = queue_get_item(&args->outpacket_queue, 0);
        for (lthread = lthread_head; lthread != NULL; lthread = lthread->next) {
            if (lthread->args.wildcard != 0)
                continue;
            if (lthread->args.listen_port != OUTP(wi).local_port ||
              strcmp(lthread->args.listen_addr, OUTP(wi).local_addr) != 0)
                continue;
            break;
        }
        if (lthread == NULL) {
            lthread = malloc(sizeof(*lthread));
            if (lthread == NULL) {
                fprintf(stderr, "lthread_mgr_run: out of mem\n");
                wi_free(wi);
                continue;
            }
            memset(lthread, '\0', sizeof(*lthread));
            lthread->args.listen_addr = strdup(OUTP(wi).local_addr);
            lthread->args.listen_port = OUTP(wi).local_port;
            if (lthread_sock_prepare(&lthread->args) != 0) {
                fprintf(stderr, "lthread_sock_prepare(%s:%d) = -1\n", lthread->args.listen_addr, lthread->args.listen_port);
                wi_free(wi);
                free(lthread->args.listen_addr);
                free(lthread);
                continue;
            }
            pthread_cond_init(&lthread->args.outpacket_queue.cond, NULL);
            pthread_mutex_init(&lthread->args.outpacket_queue.mutex, NULL);
            asprintf(&lthread->args.outpacket_queue.name, "B2B->NET (%s:%d)", lthread->args.listen_addr,
              lthread->args.listen_port);
            lthread->args.bslots = args->bslots;

            i = pthread_create(&lthread->rx_thread, NULL, (void *(*)(void *))&lthread_rx, &lthread->args);
            lthread->next = lthread_head;
            lthread_head = lthread;
        }
        queue_put_item(wi, &lthread->args.outpacket_queue);
    }
}

extern char *strcasestr (__const char *__haystack, __const char *__needle);

static int
extract_call_id(const char *buf, str *call_id)
{
    const char *cp, *cp1;
    int len;

    for (cp = buf;;) {
        cp1 = strcasestr(cp, "call-id:");
        if (cp1 == NULL) {
            cp = strcasestr(cp, "i:");
            if (cp == NULL)
                return -1;
            len = 2;
        } else {
            cp = cp1;
            len = 8;
        }
        if (cp > buf && cp[-1] != '\n' && cp[-1] != '\r') {
            cp += len;
            continue;
        }
        call_id->s = (char *)cp + len;
        while (call_id->s[0] != '\0' && call_id->s[0] != '\r' &&
          call_id->s[0] != '\n' && isspace(call_id->s[0]))
            call_id->s++;
        if (call_id->s[0] == '\0' || call_id->s[0] == '\r' || call_id->s[0] == '\n')
            return -1;
        call_id->len = 0;
        while (call_id->s[call_id->len] != '\0' && call_id->s[call_id->len] != '\r' &&
          call_id->s[call_id->len] != '\n' && !isspace(call_id->s[call_id->len]))
            call_id->len++;
        if (call_id->len == 0)
            return -1;
        return 0;
    }
}

static int
lthread_sock_prepare(struct lthread_args *args)
{
    struct sockaddr_storage ia;
    char listen_port[10];
    int n;

    sprintf(listen_port, "%d", args->listen_port);
    n = resolve(sstosa(&ia), AF_INET, args->listen_addr, listen_port, AI_PASSIVE);
    if (n != 0)
        return -1;
    args->sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (args->sock < 0)
        return -1;
    setsockopt(args->sock, SOL_SOCKET, SO_REUSEADDR, &args->sock, sizeof args->sock);
    n = bind(args->sock, sstosa(&ia), SS_LEN(&ia));
    if (n != 0) {
        printf("lthread_sock_prepare:bind(%d)\n", n);
        close(args->sock);
        return -1;
    }
    return 0;
}

static void
lthread_rx(struct lthread_args *args)
{
    int n;
    socklen_t ralen;
    size_t rsize;
    struct sockaddr_storage ia, la;
    struct wi *wi;
    pthread_t tx_thread;
    str call_id;
    struct b2bua_slot *bslot;

    if (args->wildcard == 0)
        n = pthread_create(&tx_thread, NULL, (void *(*)(void *))&lthread_tx, args);
    for (;;) {
        wi = wi_malloc(WI_INPACKET);
        if (wi == NULL) {
            fprintf(stderr, "out of mem\n");
            continue;
        }
        rsize = 8 * 1024;
        INP(wi).databuf = malloc(rsize);
        if (INP(wi).databuf == NULL) {
            fprintf(stderr, "out of mem\n");
            wi_free(wi);
            continue;
        }
        ralen = sizeof(ia);
        INP(wi).rsize = recvfrom(args->sock, INP(wi).databuf, rsize - 1, 0, sstosa(&ia), &ralen);
        if (INP(wi).rsize < 128) {
            wi_free(wi);
            /* Message is too short, just drop it already */
            continue;
        }
        INP(wi).dtime = getdtime();
        INP(wi).databuf[INP(wi).rsize] = '\0';
        if (extract_call_id((const char *)INP(wi).databuf, &call_id) != 0) {
            if (INP(wi).rsize < rsize - 1) {
                /*
                 * If incoming message size is exactly the size of the
                 * input buffer and call-id cannot be extracted this means
                 * that the message was too long and probably has been
                 * truncated as a result. Ignore it silently.
                 */
                fprintf(stderr, "can't extract Call-ID: %d\n", INP(wi).rsize);
            }
            wi_free(wi);
            continue;
        }
        bslot = b2bua_getslot(args->bslots, &call_id);
        INP(wi).remote_addr = malloc(256);
        if (INP(wi).remote_addr == NULL) {
            fprintf(stderr, "out of mem\n");
            wi_free(wi);
            continue;
        }
        INP(wi).remote_port = ntohs(satosin(&ia)->sin_port);
        addr2char_r(sstosa(&ia), INP(wi).remote_addr, 256);
        if (args->wildcard != 0) {
            INP(wi).local_addr = malloc(256);
            if (INP(wi).local_addr != NULL) {
                n = local4remote(sstosa(&ia), &la);
                addr2char_r(sstosa(&la), INP(wi).local_addr, 256);
            }
        } else {
            INP(wi).local_addr = strdup(args->listen_addr);
        }
        if (INP(wi).local_addr == NULL) {
            fprintf(stderr, "out of mem\n");
            wi_free(wi);
            continue;
        }
        INP(wi).local_port = args->listen_port;
        queue_put_item(wi, &bslot->inpacket_queue);
    }
}

static void
lthread_tx(struct lthread_args *args)
{
    int n;
    struct sockaddr_storage ia;
    struct wi *wi;

    for (;;) {
        wi = queue_get_item(&args->outpacket_queue, 0);

#ifdef DEBUG
        printf("lthread_tx: outgoing packet to %s:%s, size %d\n",
          OUTP(wi).remote_addr, OUTP(wi).remote_port, OUTP(wi).ssize);
#endif

        n = resolve(sstosa(&ia), AF_INET, OUTP(wi).remote_addr, OUTP(wi).remote_port, AI_PASSIVE);
        if (n != 0) {
            wi_free(wi);
            continue;
        }
        n = sendto(args->sock, OUTP(wi).databuf, OUTP(wi).ssize, 0,
          sstosa(&ia), SS_LEN(&ia));
#ifdef DEBUG
        printf("lthread_tx: sendto(%d)\n", n);
#endif
        wi_free(wi);
   }
}
