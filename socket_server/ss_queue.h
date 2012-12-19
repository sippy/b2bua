#ifndef _SS_QUEUE_H_
#define _SS_QUEUE_H_

#include <pthread.h>

struct wi;

struct queue
{
    struct wi *head;
    struct wi *tail;
    pthread_cond_t cond;
    pthread_mutex_t mutex;
    int length;
    char *name;
    double max_ttl;
};

int queue_init(struct queue *queue, const char *format, ...);
void queue_put_item(struct wi *wi, struct queue *);
struct wi *queue_get_item(struct queue *queue, int return_on_wake);

#endif
