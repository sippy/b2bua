#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>

#include "ss_network.h"
#include "ss_lthread.h"
#include "b2bua_socket.h"

void
queue_put_item(struct wi *wi, struct wi **queue, struct wi **queue_tail,
  pthread_mutex_t *queue_mutex, pthread_cond_t *queue_cond)
{

    pthread_mutex_lock(queue_mutex);

    wi->next = NULL;
    if (*queue == NULL) {
        *queue = wi;
        *queue_tail = wi;
    } else {
        (*queue_tail)->next = wi;
        *queue_tail = wi;
    }

    /* notify worker thread */
    pthread_cond_signal(queue_cond);

    pthread_mutex_unlock(queue_mutex);
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
    n = bind(args->sock, sstosa(&ia), SS_LEN(&ia));
    if (n != 0) {
        printf("lthread_sock_prepare:bind(%d)\n", n);
        close(args->sock);
        return -1;
    }
    return 0;
}

static void lthread_tx(struct lthread_args *);

static void
lthread_rx(struct lthread_args *args)
{
    int n, ralen, rsize;
    struct sockaddr_storage ia, la;
    struct wi *wi;
    pthread_t tx_thread;

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
        queue_put_item(wi, &(args->inpacket_queue), &(args->inpacket_queue_tail),
          &(args->inpacket_queue_mutex), &(args->inpacket_queue_cond));
    }
}

static void
lthread_tx(struct lthread_args *args)
{
    int n;
    struct sockaddr_storage ia;
    struct wi *wi;

    for (;;) {
        pthread_mutex_lock(&args->outpacket_queue_mutex);
        while (args->outpacket_queue == NULL) {
            pthread_cond_wait(&args->outpacket_queue_cond,
              &args->outpacket_queue_mutex);
        }
        wi = args->outpacket_queue;
        args->outpacket_queue = wi->next;
        pthread_mutex_unlock(&args->outpacket_queue_mutex);

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

int
main(int argc, char **argv)
{
    pthread_t lthreads[10];
    int i;
    struct lthread_args args;

    bzero(lthreads, sizeof(*lthreads));
    memset(&args, '\0', sizeof(args));
    pthread_cond_init(&args.inpacket_queue_cond, NULL);
    pthread_mutex_init(&args.inpacket_queue_mutex, NULL);
    pthread_cond_init(&args.outpacket_queue_cond, NULL);
    pthread_mutex_init(&args.outpacket_queue_mutex, NULL);
    args.listen_addr = "0.0.0.0";
    args.listen_port = 5090;
    if (lthread_sock_prepare(&args) != 0) {
        fprintf(stderr, "lthread_sock_prepare(-1)\n");
        exit(1);
    }
    i = pthread_create(&(lthreads[0]), NULL, (void *(*)(void *))&lthread_rx, &args);
    printf("%d\n", i);
    i = pthread_create(&(lthreads[1]), NULL, (void *(*)(void *))&b2bua_acceptor_run, &args);
    printf("%d\n", i);
    pthread_join(lthreads[0], NULL);
}
