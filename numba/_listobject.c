#include "_listobject.h"

static void
copy_item(NB_List *lp, char *dst, const char *src){
    memcpy(dst, src, lp->itemsize);
}

int
numba_list_new(NB_List **out, Py_ssize_t itemsize, Py_ssize_t allocated){
    NB_List *lp = malloc(aligned_size(sizeof(NB_List)));
    lp->size = 0;
    lp->itemsize = itemsize;
    lp->allocated = allocated;
    lp->items = malloc(aligned_size(lp->itemsize * allocated));

    *out = lp;
    return 0;
}

Py_ssize_t
numba_list_length(NB_List *lp) {
    return lp->size;
}

int
numba_list_setitem(NB_List *lp, Py_ssize_t index, const char *item) {
    assert(index < lp->size);
    char *loc = lp->items + lp-> itemsize * index;
    copy_item(lp, loc, item);
    return 0;
}
int
numba_list_getitem(NB_List *lp, Py_ssize_t index, char *out) {
    assert(index < lp->size);
    char *loc = lp->items + lp->itemsize * index;
    copy_item(lp, out, loc);
    return 0;
}

int
numba_list_append(NB_List *lp, const char *item) {
    if (lp->size == lp->allocated) {
        int result = numba_list_realloc(lp, lp->size + 1);
        if(result < 0) { return result; }
    }
    numba_list_setitem(lp, lp->size++ , item);
    return 0;
}

int
numba_list_realloc(NB_List *lp, Py_ssize_t newsize) {
    size_t new_allocated, num_allocated_bytes;
    /* This over-allocates proportional to the list size, making room
     * for additional growth.  The over-allocation is mild, but is
     * enough to give linear-time amortized behavior over a long
     * sequence of appends() in the presence of a poorly-performing
     * system realloc().
     * The growth pattern is:  0, 4, 8, 16, 25, 35, 46, 58, 72, 88, ...
     * Note: new_allocated won't overflow because the largest possible value
     *       is PY_SSIZE_T_MAX * (9 / 8) + 6 which always fits in a size_t.
     */
    new_allocated = (size_t)newsize + (newsize >> 3) + (newsize < 9 ? 3 : 6);
    num_allocated_bytes = new_allocated * lp->itemsize;
    lp->items = realloc(lp->items, aligned_size(num_allocated_bytes));
    if (!lp->items) { return -1; }
    lp->allocated = (Py_ssize_t)new_allocated;
    return 0;
}