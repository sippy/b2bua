/*
 * Copyright (c) 2012 Sippy Software, Inc. All rights reserved.
 *
 * This file is part of SIPPY, a free RFC3261 SIP stack and B2BUA.
 *
 * SIPPY is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * For a license to use the SIPPY software under conditions
 * other than those described here, or to purchase support for this
 * software, please contact Sippy Software, Inc. by e-mail at the
 * following addresses: sales@sippysoft.com.
 *
 * SIPPY is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.
 */

#include <fcntl.h>
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

int
append_bslot(struct b2bua_slot **bslots, int id)
{
    struct b2bua_slot *bslot;

    bslot = malloc(sizeof(*bslot));
    if (bslot == NULL)
        return (-1);
    memset(bslot, '\0', sizeof(*bslot));
    bslot->id = id;
    pthread_cond_init(&bslot->inpacket_queue.cond, NULL);
    pthread_mutex_init(&bslot->inpacket_queue.mutex, NULL);
    asprintf(&bslot->inpacket_queue.name, "NET->B2B (slot %d)", id);
    if (*bslots != NULL)
        bslot->next = *bslots;
    *bslots = bslot;
    return (0);
}

int
main(int argc, char **argv)
{
    pthread_t lthreads[10];
    int i, fd;
    struct lthread_args args;

    fd = open("/var/log/socket_server.log", O_WRONLY | O_APPEND | O_CREAT, 0);
    ss_daemon(0, fd);
    bzero(lthreads, sizeof(*lthreads));
    memset(&args, '\0', sizeof(args));
    pthread_cond_init(&args.outpacket_queue.cond, NULL);
    pthread_mutex_init(&args.outpacket_queue.mutex, NULL);
    args.outpacket_queue.name = strdup("B2B->NET (sorter)");

    append_bslot(&args.bslots, 5061);
    append_bslot(&args.bslots, 5067);
    append_bslot(&args.bslots, 5068);
    append_bslot(&args.bslots, 5069);
    append_bslot(&args.bslots, 5070);
    append_bslot(&args.bslots, 5071);

    args.listen_addr = "0.0.0.0";
    args.listen_port = 5060;
    i = pthread_create(&(lthreads[0]), NULL, (void *(*)(void *))&lthread_mgr_run, &args);
    printf("%d\n", i);
    i = pthread_create(&(lthreads[1]), NULL, (void *(*)(void *))&b2bua_acceptor_run, &args);
    printf("%d\n", i);
    pthread_join(lthreads[0], NULL);
}
