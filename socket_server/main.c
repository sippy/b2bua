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

static void
inpacket_queue_put_item(struct lthread_args *args, struct inpacket_wi *wi)
{

    pthread_mutex_lock(&args->inpacket_queue_mutex);

    wi->next = NULL;
    if (args->inpacket_queue == NULL) {
        args->inpacket_queue = wi;
        args->inpacket_queue_tail = wi;
    } else {
        args->inpacket_queue_tail->next = wi;
        args->inpacket_queue_tail = wi;
    }

    /* notify worker thread */
    pthread_cond_signal(&args->inpacket_queue_cond);

    pthread_mutex_unlock(&args->inpacket_queue_mutex);
}

static void
lthread_run(struct lthread_args *args)
{
    int n, s, ralen, rsize;
    struct sockaddr_storage ia, la;
    struct inpacket_wi *wi;

    printf("rtpp_cmd_queue_run(%s)\n", args->listen_addr);
    n = resolve(sstosa(&ia), AF_INET, args->listen_addr, "5060", AI_PASSIVE);
    printf("resolve(%d)\n", n);

    s = socket(AF_INET, SOCK_DGRAM, 0);
    printf("socket(%d)\n", s);
    n = bind(s, sstosa(&ia), SS_LEN(&ia));
    printf("bind(%d)\n", n);
    for (;;) {
        wi = malloc(sizeof(*wi));
        memset(wi, '\0', sizeof(*wi));
        rsize = 8 * 1024;
        wi->databuf = malloc(rsize);
        ralen = sizeof(ia);
        wi->rsize = recvfrom(s, wi->databuf, rsize, 0, sstosa(&ia), &ralen);
        wi->dtime = getdtime();
        wi->remote_addr = malloc(256);
        wi->remote_port = ntohs(satosin(&ia)->sin_port);
        addr2char_r(sstosa(&ia), wi->remote_addr, 256);
        wi->local_addr = malloc(256);
        n = local4remote(sstosa(&ia), &la);
        addr2char_r(sstosa(&la), wi->local_addr, 256);
        wi->local_port = args->listen_port;
        inpacket_queue_put_item(args, wi);
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
    args.listen_addr = "0.0.0.0";
    args.listen_port = 5060;
    i = pthread_create(&(lthreads[0]), NULL, (void *(*)(void *))&lthread_run, &args);
    printf("%d\n", i);
    i = pthread_create(&(lthreads[1]), NULL, (void *(*)(void *))&b2bua_acceptor_run, &args);
    printf("%d\n", i);
    pthread_join(lthreads[0], NULL);
}
