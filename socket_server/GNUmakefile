CC?=    gcc

SRCS = main.c ss_network.c b2bua_socket.c ss_lthread.c ss_util.c ss_base64.c \
	ss_queue.c
OBJS = $(SRCS:.c=.o)
LIBS = -L/usr/local/lib -lpthread -liksemel -lrt

CFLAGS += -I/usr/local/include

.c.o:
	$(CC) -c $(CFLAGS) $< -o $@

all: socket_server

socket_server: $(OBJS)
	$(CC) -o socket_server $(OBJS) $(LIBS)

clean:
	rm -f socket_server $(OBJS)

