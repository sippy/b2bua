/* Copyright (c) 2012-2014 Sippy Software, Inc. All rights reserved.
 *
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without modification,
 * are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice, this
 * list of conditions and the following disclaimer.
 *
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 * this list of conditions and the following disclaimer in the documentation and/or
 * other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 * WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
 * ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
 * (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
 * LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
 * ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
 * SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <grp.h>
#include <pwd.h>

#include "ss_defines.h"
#include "ss_network.h"
#include "ss_lthread.h"
#include "ss_queue.h"
#include "b2bua_socket.h"

extern int asprintf(char **, const char *, ...);

int
append_bslot(struct b2bua_slot **bslots, int id)
{
    struct b2bua_slot *bslot;

    bslot = malloc(sizeof(*bslot));
    if (bslot == NULL)
        return (-1);
    memset(bslot, '\0', sizeof(*bslot));
    bslot->id = id;
    if (queue_init(&bslot->inpacket_queue, "NET->B2B (slot %d)", id) != 0) {
        free(bslot);
        return (-1);
    }
    bslot->inpacket_queue.max_ttl = 33;
    if (*bslots != NULL)
        bslot->next = *bslots;
    *bslots = bslot;
    return (0);
}

static void
usage(void)
{

    fprintf(stderr, "usage: socket_server [-f] [-p pid_file] -s slot_id1 [-s slot_id2]...[-s slot_idN]\n");
    exit(1);
}

static int
parse_uname_gname(struct app_cfg *cf, char *optarg)
{
    char *cp;
    struct passwd *pp;
    struct group *gp;

    cf->stable.run_uname = optarg;
    cp = strchr(optarg, ':');
    if (cp != NULL) {
        if (cp == optarg)
            cf->stable.run_uname = NULL;
        cp[0] = '\0';
        cp++;
    }
    cf->stable.run_gname = cp;
    cf->stable.run_uid = -1;
    cf->stable.run_gid = -1;
    if (cf->stable.run_uname != NULL) {
        pp = getpwnam(cf->stable.run_uname);
        if (pp == NULL) {
            fprintf(stderr, "can't find ID for the user: %s\n", cf->stable.run_uname);
            return (-1);
        }
        cf->stable.run_uid = pp->pw_uid;
        if (cf->stable.run_gname == NULL)
            cf->stable.run_gid = pp->pw_gid;
    }
    if (cf->stable.run_gname != NULL) {
        gp = getgrnam(cf->stable.run_gname);
        if (gp == NULL) {
            fprintf(stderr, "can't find ID for the group: %s\n", cf->stable.run_gname);
            return (-1);
        }
        cf->stable.run_gid = gp->gr_gid;
    }
    return (0);
}

int
main(int argc, char **argv)
{
    pthread_t lthreads[10];
    int i, fd, nodaemon, slot_id, ch, len;
    struct lthread_args args;
    const char *pid_file;
    char *buf;
    struct app_cfg *cf;

    cf = malloc(sizeof(*cf));
    memset(cf, '\0', sizeof(*cf));

    memset(&lthreads, '\0', sizeof(lthreads));
    memset(&args, '\0', sizeof(args));

    nodaemon = 0;
    pid_file = "/var/run/socket_server.pid";
    while ((ch = getopt(argc, argv, "fs:p:u:")) != -1)
        switch (ch) {
        case 'f':
            nodaemon = 1;
            break;

        case 's':
            slot_id = strtol(optarg, (char **)NULL, 10);
            append_bslot(&args.bslots, slot_id);
            break;

        case 'p':
            pid_file = optarg;
            break;

        case 'u':
            if (parse_uname_gname(cf, optarg) != 0)
                usage();
            break;

        case '?':
        default:
            usage();
        }

    if (args.bslots == NULL) {
        fprintf(stderr, "socket_server: at least one slot is required\n");
        usage();
    }

    if (nodaemon == 0) {
        fd = open("/var/log/socket_server.log", O_WRONLY | O_APPEND | O_CREAT,
          DEFFILEMODE);
        ss_daemon(0, fd);
    }

    fd = open(pid_file, O_WRONLY | O_CREAT | O_TRUNC, DEFFILEMODE);
    if (fd >= 0) {
        len = asprintf(&buf, "%u\n", (unsigned int)getpid());
        write(fd, buf, len);
        close(fd);
        free(buf);
    } else {
        fprintf(stderr, "%s: can't open pidfile for writing\n", pid_file);
    }

    if (cf->stable.run_uname != NULL || cf->stable.run_gname != NULL) {
        if (drop_privileges(cf) != 0) {
            fprintf(stderr, "can't switch to requested user/group\n");
            exit(1);
        }
    }

    pthread_cond_init(&args.outpacket_queue.cond, NULL);
    pthread_mutex_init(&args.outpacket_queue.mutex, NULL);
    args.outpacket_queue.name = strdup("B2B->NET (sorter)");

    args.listen_addr = "0.0.0.0";
    args.listen_port = 5060;
    args.cmd_listen_addr = "127.0.0.1";
    args.cmd_listen_port = 22223;
    i = pthread_create(&(lthreads[0]), NULL, (void *(*)(void *))&lthread_mgr_run, &args);
    printf("%d\n", i);
    i = pthread_create(&(lthreads[1]), NULL, (void *(*)(void *))&b2bua_acceptor_run, &args);
    printf("%d\n", i);
    pthread_join(lthreads[0], NULL);
}
