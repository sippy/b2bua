#ifndef _SS_DEFINES_H_
#define _SS_DEFINES_H_

struct app_cfg {
    struct cfg_stable {
        char *run_uname;
        char *run_gname;
        uid_t run_uid;
        gid_t run_gid;
    } stable;
};

#endif
