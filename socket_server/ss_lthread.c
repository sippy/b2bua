#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "ss_lthread.h"
#include "ss_network.h"

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
        fprintf(stderr, "lthread_sock_prepare(-1)\n");
        exit(1);
    }
    pthread_cond_init(&lthread->args.outpacket_queue.cond, NULL);
    pthread_mutex_init(&lthread->args.outpacket_queue.mutex, NULL);
    lthread->args.inpacket_queue = args->inpacket_queue;
    lthread->args.recvonly = 1;

    i = pthread_create(&lthread->rx_thread, NULL, (void *(*)(void *))&lthread_rx, &lthread->args);
    printf("%d\n", i);
    lthread_head = lthread;
    for (;;) {
        wi = queue_get_item(&args->outpacket_queue);
        for (lthread = lthread_head; lthread != NULL; lthread = lthread->next) {
            if (lthread->args.recvonly != 0)
                continue;
            printf("lp: %d, la: %s\n", lthread->args.listen_port,
              lthread->args.listen_addr);
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
                fprintf(stderr, "lthread_sock_prepare(-1)\n");
                wi_free(wi);
                free(lthread);
                continue;
            }
            pthread_cond_init(&lthread->args.outpacket_queue.cond, NULL);
            pthread_mutex_init(&lthread->args.outpacket_queue.mutex, NULL);
            lthread->args.inpacket_queue = args->inpacket_queue;

            i = pthread_create(&lthread->rx_thread, NULL, (void *(*)(void *))&lthread_rx, &lthread->args);
            lthread->next = lthread_head;
            lthread_head = lthread;
        }
        queue_put_item(wi, &lthread->args.outpacket_queue);
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
    int n, ralen, rsize;
    struct sockaddr_storage ia, la;
    struct wi *wi;
    pthread_t tx_thread;

    if (args->recvonly == 0)
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
        INP(wi).rsize = recvfrom(args->sock, INP(wi).databuf, rsize, 0, sstosa(&ia), &ralen);
        INP(wi).dtime = getdtime();
        INP(wi).remote_addr = malloc(256);
        if (INP(wi).remote_addr == NULL) {
            fprintf(stderr, "out of mem\n");
            wi_free(wi);
            continue;
        }
        INP(wi).remote_port = ntohs(satosin(&ia)->sin_port);
        addr2char_r(sstosa(&ia), INP(wi).remote_addr, 256);
        INP(wi).local_addr = malloc(256);
        if (INP(wi).local_addr == NULL) {
            fprintf(stderr, "out of mem\n");
            wi_free(wi);
            continue;
        }
        n = local4remote(sstosa(&ia), &la);
        addr2char_r(sstosa(&la), INP(wi).local_addr, 256);
        INP(wi).local_port = args->listen_port;
        queue_put_item(wi, args->inpacket_queue);
    }
}

static void
lthread_tx(struct lthread_args *args)
{
    int n;
    struct sockaddr_storage ia;
    struct wi *wi;

    for (;;) {
        wi = queue_get_item(&args->outpacket_queue);

        printf("lthread_tx: outgoing packet to %s:%s, size %d\n",
          OUTP(wi).remote_addr, OUTP(wi).remote_port, OUTP(wi).ssize);

        n = resolve(sstosa(&ia), AF_INET, OUTP(wi).remote_addr, OUTP(wi).remote_port, AI_PASSIVE);
        if (n != 0) {
            wi_free(wi);
            continue;
        }
        n = sendto(args->sock, OUTP(wi).databuf, OUTP(wi).ssize, 0,
          sstosa(&ia), SS_LEN(&ia));
        printf("lthread_tx: sendto(%d)\n", n);
        wi_free(wi);
   }
}
