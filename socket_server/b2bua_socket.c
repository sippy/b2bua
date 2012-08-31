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
#include <unistd.h>

#include "ss_network.h"
#include "ss_lthread.h"

struct b2bua_xchg_args {
    int socket;
    struct lthread_args *largs;
};

static void b2bua_xchg_tx(struct b2bua_xchg_args *);

void
b2bua_acceptor_run(struct lthread_args *args)
{
    int n, s, ralen, btidx;
    struct sockaddr_storage ia;
    struct b2bua_xchg_args *bargs;
    pthread_t bthreads[10];

    btidx = 0;

    printf("b2bua_acceptor_run(%s)\n", args->listen_addr);
    n = resolve(sstosa(&ia), AF_INET, args->listen_addr, "22223", AI_PASSIVE);
    printf("resolve(%d)\n", n);

    s = socket(AF_INET, SOCK_STREAM, 0);
    printf("socket(%d)\n", s);
    n = bind(s, sstosa(&ia), SS_LEN(&ia));
    printf("bind(%d)\n", n);
    n = listen(s, 32);
    for (;;) {
        ralen = sizeof(ia);
        n = accept(s, sstosa(&ia), &ralen);
        printf("accept(%d)\n", n);
        bargs = malloc(sizeof(*bargs));
        bargs->largs = args;
        bargs->socket = n;
        n = pthread_create(&(bthreads[btidx]), NULL, (void *(*)(void *))&b2bua_xchg_tx, bargs);
        btidx += 1;
    }
}

static void
b2bua_xchg_tx(struct b2bua_xchg_args *bargs)
{
    struct pollfd pfds[1];
    int i;
    double eptime;
    struct inpacket_wi *wi;
    char b64_databuf[8 * 1024];

    pfds[0].fd = bargs->socket;
    for (;;) {
        pthread_mutex_lock(&bargs->largs->inpacket_queue_mutex);
        while (bargs->largs->inpacket_queue == NULL) {
            pthread_cond_wait(&bargs->largs->inpacket_queue_cond,
              &bargs->largs->inpacket_queue_mutex);
        }
        wi = bargs->largs->inpacket_queue;
        bargs->largs->inpacket_queue = wi->next;
        pthread_mutex_unlock(&bargs->largs->inpacket_queue_mutex);
        printf("incoming size=%d, from=%s:%d, to=%s\n", wi->rsize,
          wi->remote_addr, wi->remote_port, wi->local_addr);

        for (;;) {
            pfds[0].events = POLLOUT;
            pfds[0].revents = 0;

            i = poll(pfds, 1, INFTIM);
            if (i == 0)
                continue;
            if (i < 0 && errno == EINTR)
                continue;
            eptime = getdtime();
            if (i < 0)
                abort();
            if ((pfds[0].revents & POLLOUT) != 0)
                break;
        }
        printf("b2bua_xchg_tx, POLLOUT\n");
        i = b64_ntop(wi->databuf, wi->rsize, b64_databuf, sizeof(b64_databuf));
        dprintf(bargs->socket, "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n" \
          "<incoming_packet\n" \
          "\tsrc_addr=\"%s\"\n" \
          "\tsrc_port=\"%d\"\n" \
          "\tdst_addr=\"%s\"\n" \
          "\tdst_port=\"%d\"\n" \
          "\trtime=\"%f\"\n" \
          "\tmsg=\"%.*s\"\n" \
          "/>\n", wi->remote_addr, wi->remote_port, wi->local_addr, wi->local_port, \
          wi->dtime, i, b64_databuf);
        free(wi->databuf);
        free(wi->remote_addr);
        free(wi->local_addr);
        free(wi);
    }
}
