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
queue_put_item(struct wi *wi, struct queue *queue)
{

    pthread_mutex_lock(&queue->mutex);

    wi->next = NULL;
    if (queue->head == NULL) {
        queue->head = wi;
        queue->tail = wi;
    } else {
        queue->tail->next = wi;
        queue->tail = wi;
    }

    /* notify worker thread */
    pthread_cond_signal(&queue->cond);

    pthread_mutex_unlock(&queue->mutex);
}

struct wi *
queue_get_item(struct queue *queue)
{
    struct wi *wi;

    pthread_mutex_lock(&queue->mutex);
    while (queue->head == NULL) {
        pthread_cond_wait(&queue->cond, &queue->mutex);
    }
    wi = queue->head;
    queue->head = wi->next;
    pthread_mutex_unlock(&queue->mutex);

    return wi;
}

int
main(int argc, char **argv)
{
    pthread_t lthreads[10];
    int i;
    struct lthread_args args;

    bzero(lthreads, sizeof(*lthreads));
    memset(&args, '\0', sizeof(args));
    pthread_cond_init(&args.outpacket_queue.cond, NULL);
    pthread_mutex_init(&args.outpacket_queue.mutex, NULL);
    args.inpacket_queue = malloc(sizeof(*args.inpacket_queue));
    if (args.inpacket_queue == NULL) {
        fprintf(stderr, "out of mem\n");
        exit(1);
    }
    pthread_cond_init(&args.inpacket_queue->cond, NULL);
    pthread_mutex_init(&args.inpacket_queue->mutex, NULL);
    args.listen_addr = "0.0.0.0";
    args.listen_port = 5060;
    i = pthread_create(&(lthreads[0]), NULL, (void *(*)(void *))&lthread_mgr_run, &args);
    printf("%d\n", i);
    i = pthread_create(&(lthreads[1]), NULL, (void *(*)(void *))&b2bua_acceptor_run, &args);
    printf("%d\n", i);
    pthread_join(lthreads[0], NULL);
}
