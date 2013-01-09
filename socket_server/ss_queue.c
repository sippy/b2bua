#include <pthread.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "ss_queue.h"
#include "ss_lthread.h"

extern int vasprintf(char **, const char *, va_list);

int
queue_init(struct queue *queue, const char *fmt, ...)
{
    va_list ap;

    memset(queue, '\0', sizeof(*queue));
    if (pthread_cond_init(&queue->cond, NULL) != 0)
        return (-1);
    if (pthread_mutex_init(&queue->mutex, NULL) != 0)
        return (-1);
    va_start(ap, fmt);
    vasprintf(&queue->name, fmt, ap);
    va_end(ap);
    if (queue->name == NULL)
        return (-1);
    return (0);
}

void
queue_put_item(struct wi *wi, struct queue *queue)
{
    struct wi *tmpwi, *nextwi, *prevwi;
    double cutoff_time;

    pthread_mutex_lock(&queue->mutex);

    if (wi->wi_type == WI_INPACKET && queue->max_ttl > 0 && queue->length > 0
      && queue->length % 100 == 0) {
        cutoff_time = INP(wi).dtime - queue->max_ttl;
        prevwi = NULL;
        for (tmpwi = queue->head; tmpwi != NULL; tmpwi = nextwi) {
            nextwi = tmpwi->next;
            if (INP(tmpwi).dtime < cutoff_time) {
                if (queue->head == tmpwi)
                    queue->head = nextwi;
                if (queue->tail == tmpwi)
                    queue->tail = prevwi;
                queue->length -= 1;
                wi_free(wi);
            }
        }
    }
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
        fprintf(stderr, "queue(%s): length %d\n", queue->name, queue->length);

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
