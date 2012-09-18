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
    queue->length += 1;
    if (queue->length > 99 && queue->length % 100 == 0)
        fprintf(stderr, "queue(%p): length %d\n", queue, queue->length);

    /* notify worker thread */
    pthread_cond_signal(&queue->cond);

    pthread_mutex_unlock(&queue->mutex);
}

struct wi *
queue_get_item(struct queue *queue, int return_on_wake)
{
    struct wi *wi;

    pthread_mutex_lock(&queue->mutex);
    while (queue->head == NULL) {
        pthread_cond_wait(&queue->cond, &queue->mutex);
        if (queue->head == NULL && return_on_wake != 0) {
            pthread_mutex_unlock(&queue->mutex);
            return NULL;
        }
    }
    wi = queue->head;
    queue->head = wi->next;
    if (queue->head == NULL)
        queue->tail = NULL;
    queue->length -= 1;
    pthread_mutex_unlock(&queue->mutex);

    return wi;
}

int
main(int argc, char **argv)
{
    pthread_t lthreads[10];
    int i;
    struct lthread_args args;
    struct b2bua_slot *bslot;

    bzero(lthreads, sizeof(*lthreads));
    memset(&args, '\0', sizeof(args));
    pthread_cond_init(&args.outpacket_queue.cond, NULL);
    pthread_mutex_init(&args.outpacket_queue.mutex, NULL);
    bslot = malloc(sizeof(*bslot));
    memset(bslot, '\0', sizeof(*bslot));
    bslot->id = 5061;
    pthread_cond_init(&bslot->inpacket_queue.cond, NULL);
    pthread_mutex_init(&bslot->inpacket_queue.mutex, NULL);
    bslot->next = malloc(sizeof(*bslot));
    memset(bslot->next, '\0', sizeof(*bslot));
    bslot->next->id = 5067;
    pthread_cond_init(&bslot->next->inpacket_queue.cond, NULL);
    pthread_mutex_init(&bslot->next->inpacket_queue.mutex, NULL);
    args.listen_addr = "0.0.0.0";
    args.listen_port = 5060;
    args.bslots = bslot;
    i = pthread_create(&(lthreads[0]), NULL, (void *(*)(void *))&lthread_mgr_run, &args);
    printf("%d\n", i);
    i = pthread_create(&(lthreads[1]), NULL, (void *(*)(void *))&b2bua_acceptor_run, &args);
    printf("%d\n", i);
    pthread_join(lthreads[0], NULL);
}
