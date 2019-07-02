from __future__ import print_function, absolute_import, division

from itertools import product

import numpy as np

from numba import njit
from numba import int32, types
from numba.typed import List, Dict
from numba.utils import IS_PY3
from numba.errors import TypingError
from numba.typing.typeof import typeof
from .support import TestCase, MemoryLeakMixin, unittest

from numba.unsafe.refcount import get_refcount

skip_py2 = unittest.skipUnless(IS_PY3, reason='not supported in py2')


def to_tl(l):
    """ Convert cpython list to typed-list. """
    tl = List.empty_list(int32)
    for k in l:
        tl.append(k)
    return tl


class TestTypedList(MemoryLeakMixin, TestCase):

    def test_basic(self):
        l = List.empty_list(int32)
        # len
        self.assertEqual(len(l), 0)
        # append
        l.append(0)
        # len
        self.assertEqual(len(l), 1)
        # setitem
        l.append(0)
        l.append(0)
        l[0] = 10
        l[1] = 11
        l[2] = 12
        # getitem
        self.assertEqual(l[0], 10)
        self.assertEqual(l[1], 11)
        self.assertEqual(l[2], 12)
        self.assertEqual(l[-3], 10)
        self.assertEqual(l[-2], 11)
        self.assertEqual(l[-1], 12)
        # __iter__
        # the default __iter__ from MutableSequence will raise an IndexError
        # via __getitem__ and thus leak an exception, so this shouldn't
        for i in l:
            pass
        # contains
        self.assertTrue(10 in l)
        self.assertFalse(0 in l)
        # count
        l.append(12)
        self.assertEqual(l.count(0), 0)
        self.assertEqual(l.count(10), 1)
        self.assertEqual(l.count(12), 2)
        # pop
        self.assertEqual(len(l), 4)
        self.assertEqual(l.pop(), 12)
        self.assertEqual(len(l), 3)
        self.assertEqual(l.pop(1), 11)
        self.assertEqual(len(l), 2)
        # extend
        l.extend((100, 200, 300))
        self.assertEqual(len(l), 5)
        self.assertEqual(list(l), [10, 12, 100, 200, 300])
        # insert
        l.insert(0, 0)
        self.assertEqual(list(l), [0, 10, 12, 100, 200, 300])
        l.insert(3, 13)
        self.assertEqual(list(l), [0, 10, 12, 13, 100, 200, 300])
        l.insert(100, 400)
        self.assertEqual(list(l), [0, 10, 12, 13, 100, 200, 300, 400])
        # remove
        l.remove(0)
        l.remove(400)
        l.remove(13)
        self.assertEqual(list(l), [10, 12, 100, 200, 300])
        # clear
        l.clear()
        self.assertEqual(len(l), 0)
        self.assertEqual(list(l), [])
        # reverse
        l.extend(tuple(range(10, 20)))
        l.reverse()
        self.assertEqual(list(l), list(range(10, 20))[::-1])
        # copy
        new = l.copy()
        self.assertEqual(list(new), list(range(10, 20))[::-1])
        # equal
        self.assertEqual(l, new)
        # not equal
        new[-1] = 42
        self.assertNotEqual(l, new)
        # index
        self.assertEqual(l.index(15), 4)


class StuartsTests(MemoryLeakMixin, TestCase):

    # --------------------------------------------------------------------------
    def test_init_1(self):
        self.disable_leak_check()

        @njit
        def foo():
            List.empty_list(types.NoneType)

        with self.assertRaises(TypeError) as raises:
            foo.py_func()
        self.assertIn(
            "*itemty* must be of a Type instance",
            str(raises.exception),
        )

        # FIXME this doesn't fail as a TypeError because types.NoneType isn't
        # available in a jit context
        with self.assertRaises(TypeError) as raises:
            foo()
        self.assertIn(
            "*itemty* must be of a Type instance",
            str(raises.exception),
        )

    def test_init_2(self):
        self.disable_leak_check()

        @njit
        def foo():
            List.empty_list(1j)

        with self.assertRaises(TypeError) as raises:
            foo.py_func()
        self.assertIn(
            "*itemty* must be of a Type instance",
            str(raises.exception),
        )

        # FIXME: this doesn't fail, 1j comes in as numba.types.scalars.Complex
        # which is a subtype of Type
        with self.assertRaises(TypeError) as raises:
            foo.py_func()
        self.assertIn(
            "*itemty* must be of a Type instance",
            str(raises.exception),
        )

    def test_init_3(self):
        self.disable_leak_check()
        @njit
        def foo():
            ty1 = List.empty_list(types.int64)
            ty2 = List.empty_list(ty1)
            ty3 = List.empty_list(ty2)
            _ = List.empty_list(ty3)

        with self.assertRaises(TypeError) as raises:
            foo.py_func()
        self.assertIn(
            "*itemty* must be of a Type instance",
            str(raises.exception),
        )

        with self.assertRaises(TypeError) as raises:
            foo.py_func()
        self.assertIn(
            "*itemty* must be of a Type instance",
            str(raises.exception),
        )

    def test_init_4(self):
        List.empty_list(types.Array(types.float64, 4, 'C'))

    @unittest.skip
    def test_init_5(self):
        # fails during lowering, expect similar issue to #4.
        # FIXME: bug in dictobject equals method, doesn't handle numpy arrays
        List.empty_list(Dict.empty(int32, types.Array(types.float64, 4, 'C')))

    # --------------------------------------------------------------------------
    # @unittest.skip
    def test_append_1(self):
        # self reference mutation
        # Fail: wrong answer
        # FIXME: cpython runs away with this one, unclear what Numba should do
        # NOTE: it's okay to be restrictive and raise on mutation until someone complain
        @njit
        def impl():
            l = List.empty_list(int32)
            for i in range(10):
                l.append(i)

            for x in l:
                l.append(x)
            return l

        expected = impl.py_func()
        got = impl()
        self.assertEqual(expected, got)

    # @unittest.skip
    def test_append_2(self):
        # check mutation of pointer ref is transparent
        # Fail: AttributeError: 'ListType' object has no attribute 'instance_type'
        # FIXME: intention of test unclear, types should probably be defined
        # outside jitted scope
        @njit
        def impl():
            ty = List.empty_list(types.unicode_type)
            l = List.empty_list(ty)

            z = List.empty_list(types.unicode_type)
            for i in range(10):
                z.append('a' * 2)

            for i in z:
                l.append(z)
            return l

        expected = impl.py_func()
        got = impl()
        self.assertEqual(expected, got)

    @unittest.skip
    def test_append_3(self):
        # self reference mutation
        # Fail: wrong answer
        # FIXME: same as test_append_1
        @njit
        def impl():
            l = List.empty_list(int32)
            for i in range(10):
                l.append(i)

            for x in l:
                l.append(x)
            return l

        expected = impl.py_func()
        got = impl()
        self.assertEqual(expected, got)

    # --------------------------------------------------------------------------

    def test_count_1(self):
        # weird typing failure, not sure it's the fault of list
        # FIXED? unable to reproduce
        @njit
        def impl():
            l = List.empty_list(int32)
            for i in range(10):
                l.append(i)

            l.append(l.count(1))
            return l

        expected = impl.py_func()
        got = impl()
        self.assertEqual(expected, got)

    def test_count_2(self):
        # this sometimes is different to cpython `['abc', 'def', 'ghi'].count('abc\0')
        # FIXED? unable to reproduce but added cpython snippet and code
        @njit
        def impl():
            l = List.empty_list(types.unicode_type)
            l.append('abc')
            l.append('def')
            l.append('ghi')
            return l.count('abc\0')

        expected = impl.py_func()
        got = impl()
        cpython_got = ['abc', 'def', 'ghi'].count('abc\0')
        self.assertEqual(expected, got)
        self.assertEqual(expected, cpython_got)
        self.assertEqual(got, cpython_got)

    # --------------------------------------------------------------------------

    def test_extend_1(self):
        # this is broken behaviour, expect .extend() needs to copy if self
        # referent
        # FIXED in code, no change to test needed
        @njit
        def impl():
            l = List.empty_list(types.int32)
            for x in range(10):
                l.append(x)
            l.extend(l)
            return l

        expected = impl.py_func()
        got = impl()
        self.assertEqual(expected, got)

    # --------------------------------------------------------------------------

    def test_index_1(self):
        # index not implemented
        # FIXED in code, no change to test needed
        @njit
        def impl():
            l = List.empty_list(types.int32)
            l.append(0)
            return l.index(0)

        expected = impl.py_func()
        got = impl()
        self.assertEqual(expected, got)

    # --------------------------------------------------------------------------

    def test_insert_1(self):
        # should raise something about the index needing to be an int
        # FIXED test, exception now raised.
        self.disable_leak_check()
        @njit
        def impl():
            l = List.empty_list(types.int32)
            l.insert('a', 0)
            return l

        with self.assertRaises(TypingError) as raises:
            impl.py_func()
        self.assertIn(
            "list insert indices must be signed integers",
            str(raises.exception),
        )
        with self.assertRaises(TypingError) as raises:
            impl()
        self.assertIn(
            "list insert indices must be signed integers",
            str(raises.exception),
        )

    def test_insert_2(self):
        # ok, stressing expansion on both sides and insertion in existing
        @njit
        def impl():
            l = List.empty_list(types.int32)
            l.append(0)
            for i in range(1, 3):
                for x in range(-i * 10, i * 10):
                    l.insert(x, x * i)
            return l

        def py_impl():
            l = []
            l.append(0)
            for i in range(1, 3):
                for x in range(-i * 10, i * 10):
                    l.insert(x, x * i)
            return l

        expected = py_impl()
        got = impl()
        self.assertEqual(len(expected), len(got))
        for x, y in zip(expected, got):
            self.assertEqual(x, y)

    # --------------------------------------------------------------------------

    def test_pop_1(self):
        # should raise message "pop from empty list"
        # FIXED test, exception now raised.
        self.disable_leak_check()
        @njit
        def impl():
            l = List.empty_list(types.int32)
            l.pop()
            return l

        with self.assertRaises(IndexError) as raises:
            impl.py_func()
        self.assertIn(
            "pop from empty list",
            str(raises.exception),
        )
        with self.assertRaises(IndexError) as raises:
            impl()
        self.assertIn(
            "pop from empty list",
            str(raises.exception),
        )

    def test_pop_2(self):
        # should raise message "pop index out of range"
        # FIXED test, exception now raised, error message not exactly right,
        # but I reckon this is O.K.
        self.disable_leak_check()
        @njit
        def impl():
            l = List.empty_list(types.int32)
            l.append(0)
            l.pop(1)
            return l

        with self.assertRaises(IndexError) as raises:
            impl.py_func()
        self.assertIn(
            "list index out of range",
            str(raises.exception),
        )
        with self.assertRaises(IndexError) as raises:
            impl()
        self.assertIn(
            "list index out of range",
            str(raises.exception),
        )

    def test_pop_3(self):
        # test drain and rebuilt
        @njit
        def impl():
            l = List.empty_list(types.int32)
            for x in range(6):
                l.append(x)
            for x in range(6):
                l.pop()
            for x in range(12):
                l.append(x)
            for x in range(6):
                l.pop(6 - x)
            return l

        expected = impl.py_func()
        got = impl()
        self.assertEqual(expected, got)

    # --------------------------------------------------------------------------

    def test_remove_1(self):
        @njit
        def impl():
            l = List.empty_list(types.int32)
            for x in range(6):
                l.append(0)
            for x in range(6):
                l.append(1)
            for x in range(6):
                l.remove(1)
            return l

        expected = impl.py_func()
        got = impl()
        self.assertEqual(expected, got)

    @unittest.skip
    def test_remove_2(self):
        # lowering error
        # FIXME: intention of test unclear
        @njit
        def impl():
            l = List.empty_list(types.List(types.int32))
            inner1 = List.empty_list(types.int32)
            inner2 = List.empty_list(types.int32)
            rem = List.empty_list(types.int32)
            for x in range(3):
                inner1.append(x)
                inner2.append(2 * x)
                rem.append(x)

            l.append(inner1)
            l.append(inner2)
            l.remove(rem)

            return l

        expected = impl.py_func()
        got = impl()
        self.assertEqual(expected, got)

    # --------------------------------------------------------------------------

    def test_reverse_1(self):
        @njit
        def impl():
            l = List.empty_list(types.int32)
            for x in range(20):
                l.append(x)

            l.reverse()

            for x in range(17):
                l.append(x)

            l.reverse()

            return l

        expected = impl.py_func()
        got = impl()
        self.assertEqual(expected, got)

    # --------------------------------------------------------------------------

    @unittest.skip
    def test_sort_1(self):
        # sort() needs writing
        # FIXME: sort may not be implemented in this release cycle
        @njit
        def impl():
            l = List.empty_list(types.int32)
            for x in range(20):
                l.append(x)

            l.reverse()
            l.sort()

            return l

        expected = impl.py_func()
        got = impl()
        self.assertEqual(expected, got)

    # --------------------------------------------------------------------------

    def test_compiled(self):
        @njit
        def producer():
            l = List.empty_list(int32)
            l.append(23)
            return l

        @njit
        def consumer(l):
            return l[0]

        l = producer()
        val = consumer(l)
        self.assertEqual(val, 23)

    def test_getitem_slice(self):
        """ Test getitem using a slice.

        This tests suffers from combinatorial explosion, so we parametrize it
        and compare results agains the regular list in a quasi fuzzing approach.

        """
        # initialize regular list
        rl = list(range(10, 20))
        # initialize typed list
        tl = List.empty_list(int32)
        for i in range(10, 20):
            tl.append(i)
        # define the ranges
        start_range = list(range(-20, 30))
        stop_range = list(range(-20, 30))
        step_range = [-5, -4, -3, -2, -1, 1, 2, 3, 4, 5]

        # check that they are the same initially
        self.assertEqual(rl, list(tl))
        # check that copy by slice works, no start, no stop, no step
        self.assertEqual(rl[:], list(tl[:]))

        # start only
        for sa in start_range:
            self.assertEqual(rl[sa:], list(tl[sa:]))
        # stop only
        for so in stop_range:
            self.assertEqual(rl[:so], list(tl[:so]))
        # step only
        for se in step_range:
            self.assertEqual(rl[::se], list(tl[::se]))

        # start and stop
        for sa, so in product(start_range, stop_range):
            self.assertEqual(rl[sa:so], list(tl[sa:so]))
        # start and step
        for sa, se in product(start_range, step_range):
            self.assertEqual(rl[sa::se], list(tl[sa::se]))
        # stop and step
        for so, se in product(stop_range, step_range):
            self.assertEqual(rl[:so:se], list(tl[:so:se]))

        # start, stop and step
        for sa, so, se in product(start_range, stop_range, step_range):
            self.assertEqual(rl[sa:so:se], list(tl[sa:so:se]))

    def test_setitem_slice(self):
        """ Test setitem using a slice.

        This tests suffers from combinatorial explosion, so we parametrize it
        and compare results agains the regular list in a quasi fuzzing approach.

        """

        def setup(start=10, stop=20):
            # initialize regular list
            rl_ = list(range(start, stop))
            # intialize typed list
            tl_ = List.empty_list(int32)
            # populate typed list
            for i in range(start, stop):
                tl_.append(i)
            # check they are the same
            self.assertEqual(rl_, list(tl_))
            return rl_, tl_


        ### Simple slicing ###

        # assign to itself
        rl, tl = setup()
        rl[:], tl[:] = rl, tl
        self.assertEqual(rl, list(tl))

        # extend self
        rl, tl = setup()
        rl[len(rl):], tl[len(tl):] = rl, tl
        self.assertEqual(rl, list(tl))
        # prepend self
        rl, tl = setup()
        rl[:0], tl[:0] = rl, tl
        self.assertEqual(rl, list(tl))
        # partial assign to self, with equal length
        rl, tl = setup()
        rl[3:5], tl[3:5] = rl[6:8], tl[6:8]
        self.assertEqual(rl, list(tl))
        # partial assign to self, with larger slice
        rl, tl = setup()
        rl[3:5], tl[3:5] = rl[6:9], tl[6:9]
        self.assertEqual(rl, list(tl))
        # partial assign to self, with smaller slice
        rl, tl = setup()
        rl[3:5], tl[3:5] = rl[6:7], tl[6:7]
        self.assertEqual(rl, list(tl))

        # extend
        rl, tl = setup()
        rl[len(rl):], tl[len(tl):] = list(range(110, 120)), to_tl(range(110,120))
        self.assertEqual(rl, list(tl))
        # extend empty
        rl, tl = setup(0, 0)
        rl[len(rl):], tl[len(tl):] = list(range(110, 120)), to_tl(range(110,120))
        self.assertEqual(rl, list(tl))
        # extend singleton
        rl, tl = setup(0, 1)
        rl[len(rl):], tl[len(tl):] = list(range(110, 120)), to_tl(range(110,120))
        self.assertEqual(rl, list(tl))

        # prepend
        rl, tl = setup()
        rl[:0], tl[:0] = list(range(110, 120)), to_tl(range(110,120))
        self.assertEqual(rl, list(tl))
        # prepend empty
        rl, tl = setup(0,0)
        rl[:0], tl[:0] = list(range(110, 120)), to_tl(range(110,120))
        self.assertEqual(rl, list(tl))
        # prepend singleton
        rl, tl = setup(0,1)
        rl[:0], tl[:0] = list(range(110, 120)), to_tl(range(110,120))
        self.assertEqual(rl, list(tl))

        # simple equal length assignment, just replace
        rl, tl = setup()
        rl[1:3], tl[1:3] = [100, 200], to_tl([100, 200])
        self.assertEqual(rl, list(tl))

        # slice for assignment is larger, need to replace and insert
        rl, tl = setup()
        rl[1:3], tl[1:3] = [100, 200, 300, 400], to_tl([100, 200, 300, 400])
        self.assertEqual(rl, list(tl))

        # slice for assignment is smaller, need to replace and delete
        rl, tl = setup()
        rl[1:3], tl[1:3] = [100], to_tl([100])
        self.assertEqual(rl, list(tl))

        # slice for assignment is smaller and item is empty, need to delete
        rl, tl = setup()
        rl[1:3], tl[1:3] = [], to_tl([])
        self.assertEqual(rl, list(tl))

        # Synonym for clear
        rl, tl = setup()
        rl[:], tl[:] = [], to_tl([])
        self.assertEqual(rl, list(tl))

        ### Extended slicing ###

        # replace every second element
        rl, tl = setup()
        rl[::2], tl[::2] = [100,200,300,400,500], to_tl([100,200,300,400,500])
        self.assertEqual(rl, list(tl))
        # replace every second element, backwards
        rl, tl = setup()
        rl[::-2], tl[::-2] = [100,200,300,400,500], to_tl([100,200,300,400,500])
        self.assertEqual(rl, list(tl))

        # reverse assign to itself
        rl, tl = setup()
        rl[::-1], tl[::-1] = rl, tl
        self.assertEqual(rl, list(tl))

    def test_setitem_slice_value_error(self):
        self.disable_leak_check()

        tl = List.empty_list(int32)
        for i in range(10,20):
            tl.append(i)

        assignment = List.empty_list(int32)
        for i in range(1, 4):
            assignment.append(i)

        with self.assertRaises(ValueError) as raises:
            tl[8:3:-1] = assignment
        self.assertIn(
            "length mismatch for extended slice and sequence",
            str(raises.exception),
        )

    def test_delitem_slice(self):
        """ Test delitem using a slice.

        This tests suffers from combinatorial explosion, so we parametrize it
        and compare results agains the regular list in a quasi fuzzing approach.

        """

        def setup(start=10, stop=20):
            # initialize regular list
            rl_ = list(range(start, stop))
            # intialize typed list
            tl_ = List.empty_list(int32)
            # populate typed list
            for i in range(start, stop):
                tl_.append(i)
            # check they are the same
            self.assertEqual(rl_, list(tl_))
            return rl_, tl_

        # define the ranges
        start_range = list(range(-20, 30))
        stop_range = list(range(-20, 30))
        step_range = [-5, -4, -3, -2, -1, 1, 2, 3, 4, 5]

        rl, tl = setup()
        # check that they are the same initially
        self.assertEqual(rl, list(tl))
        # check that deletion of the whole list by slice works
        del rl[:]
        del tl[:]
        self.assertEqual(rl, list(tl))

        # start only
        for sa in start_range:
            rl, tl = setup()
            del rl[sa:]
            del tl[sa:]
            self.assertEqual(rl, list(tl))
        # stop only
        for so in stop_range:
            rl, tl = setup()
            del rl[:so]
            del tl[:so]
            self.assertEqual(rl, list(tl))
        # step only
        for se in step_range:
            rl, tl = setup()
            del rl[::se]
            del tl[::se]
            self.assertEqual(rl, list(tl))

        # start and stop
        for sa, so in product(start_range, stop_range):
            rl, tl = setup()
            del rl[sa:so]
            del tl[sa:so]
            self.assertEqual(rl, list(tl))
        # start and step
        for sa, se in product(start_range, step_range):
            rl, tl = setup()
            del rl[sa::se]
            del tl[sa::se]
            self.assertEqual(rl, list(tl))
        # stop and step
        for so, se in product(stop_range, step_range):
            rl, tl = setup()
            del rl[:so:se]
            del tl[:so:se]
            self.assertEqual(rl, list(tl))

        # start, stop and step
        for sa, so, se in product(start_range, stop_range, step_range):
            rl, tl = setup()
            del rl[sa:so:se]
            del tl[sa:so:se]
            self.assertEqual(rl, list(tl))


class TestExtend(MemoryLeakMixin, TestCase):

    def test_extend_other(self):
        @njit
        def impl(other):
            l = List.empty_list(types.int32)
            for x in range(10):
                l.append(x)
            l.extend(other)
            return l

        other = List.empty_list(types.int32)
        for x in range(10):
            other.append(x)

        expected = impl.py_func(other)
        got = impl(other)
        self.assertEqual(expected, got)

    def test_extend_self(self):
        @njit
        def impl():
            l = List.empty_list(types.int32)
            for x in range(10):
                l.append(x)
            l.extend(l)
            return l

        expected = impl.py_func()
        got = impl()
        self.assertEqual(expected, got)

    def test_extend_tuple(self):
        @njit
        def impl():
            l = List.empty_list(types.int32)
            for x in range(10):
                l.append(x)
            l.extend((100,200,300))
            return l

        expected = impl.py_func()
        got = impl()
        self.assertEqual(expected, got)


@njit
def cmp(a, b):
    return a < b, a <= b, a == b, a != b, a >= b, a > b


class TestComparisons(MemoryLeakMixin, TestCase):

    def _cmp_dance(self, expected, pa, pb, na, nb):
        # interpreter with regular list
        self.assertEqual(cmp.py_func(pa, pb), expected)

        # interpreter with typed-list
        py_got = cmp.py_func(na, nb)
        self.assertEqual(py_got, expected)

        # compiled with typed-list
        jit_got = cmp(na, nb)
        self.assertEqual(jit_got, expected)

    def test_empty_vs_empty(self):
        pa, pb = [], []
        na, nb = to_tl(pa), to_tl(pb)
        expected = False, True, True, False, True, False
        self._cmp_dance(expected, pa, pb, na, nb)

    def test_empty_vs_singleton(self):
        pa, pb = [], [0]
        na, nb = to_tl(pa), to_tl(pb)
        expected = True, True, False, True, False, False
        self._cmp_dance(expected, pa, pb, na, nb)

    def test_singleton_vs_empty(self):
        pa, pb = [0], []
        na, nb = to_tl(pa), to_tl(pb)
        expected = False, False, False, True, True, True
        self._cmp_dance(expected, pa, pb, na, nb)

    def test_singleton_vs_singleton_equal(self):
        pa, pb = [0], [0]
        na, nb = to_tl(pa), to_tl(pb)
        expected = False, True, True, False, True, False
        self._cmp_dance(expected, pa, pb, na, nb)

    def test_singleton_vs_singleton_less_than(self):
        pa, pb = [0], [1]
        na, nb = to_tl(pa), to_tl(pb)
        expected = True, True, False, True, False, False
        self._cmp_dance(expected, pa, pb, na, nb)

    def test_singleton_vs_singleton_greater_than(self):
        pa, pb = [1], [0]
        na, nb = to_tl(pa), to_tl(pb)
        expected = False, False, False, True, True, True
        self._cmp_dance(expected, pa, pb, na, nb)

    def test_equal(self):
        pa, pb = [1, 2, 3], [1, 2, 3]
        na, nb = to_tl(pa), to_tl(pb)
        expected = False, True, True, False, True, False
        self._cmp_dance(expected, pa, pb, na, nb)

    def test_first_shorter(self):
        pa, pb = [1, 2], [1, 2, 3]
        na, nb = to_tl(pa), to_tl(pb)
        expected = True, True, False, True, False, False
        self._cmp_dance(expected, pa, pb, na, nb)

    def test_second_shorter(self):
        pa, pb = [1, 2, 3], [1, 2]
        na, nb = to_tl(pa), to_tl(pb)
        expected = False, False, False, True, True, True
        self._cmp_dance(expected, pa, pb, na, nb)

    def test_first_less_than(self):
        pa, pb = [1, 2, 2], [1, 2, 3]
        na, nb = to_tl(pa), to_tl(pb)
        expected = True, True, False, True, False, False
        self._cmp_dance(expected, pa, pb, na, nb)

    def test_first_greater_than(self):
        pa, pb = [1, 2, 3], [1, 2, 2]
        na, nb = to_tl(pa), to_tl(pb)
        expected = False, False, False, True, True, True
        self._cmp_dance(expected, pa, pb, na, nb)

    def test_typing_mimatch(self):
        self.disable_leak_check()
        l = to_tl([1, 2, 3])

        with self.assertRaises(TypingError) as raises:
            cmp.py_func(l, 1)
        self.assertIn(
            "list can only be compared to list",
            str(raises.exception),
        )
        with self.assertRaises(TypingError) as raises:
            cmp(l, 1)
        self.assertIn(
            "list can only be compared to list",
            str(raises.exception),
        )


class TestListInferred(TestCase):

    def test_simple_refine(self):
        @njit
        def foo():
            l = List()
            l.append(1)
            return l

        expected = foo.py_func()
        got = foo()
        self.assertEqual(expected, got)
        self.assertEqual(list(got), [1])
        self.assertEqual(typeof(got).item_type, typeof(1))


class TestListRefctTypes(MemoryLeakMixin, TestCase):

    @skip_py2
    def test_str_item(self):
        @njit
        def foo():
            l = List.empty_list(types.unicode_type)
            for s in ("a", "ab", "abc", "abcd"):
                l.append(s)
            return l

        l = foo()
        expected = ["a", "ab", "abc", "abcd"]
        for i, s in enumerate(expected):
            self.assertEqual(l[i], s)
        self.assertEqual(list(l), expected)
        # Test insert replacement
        l[3] = 'uxyz'
        self.assertEqual(l[3], 'uxyz')
        # Test list growth
        nelem = 100
        for i in range(4, nelem):
            l.append(str(i))
            self.assertEqual(l[i], str(i))

    @skip_py2
    def test_str_item_refcount_replace(self):
        @njit
        def foo():
            # use some tricks to make ref-counted unicode
            i, j = 'ab', 'c'
            a = i + j
            m, n = 'zy', 'x'
            z = m + n
            l = List.empty_list(types.unicode_type)
            l.append(a)
            # This *should* dec' a and inc' z thus tests that items that are
            # replaced are also dec'ed.
            l[0] = z
            ra, rz = get_refcount(a), get_refcount(z)
            return l, ra, rz

        l, ra, rz = foo()
        self.assertEqual(l[0], "zyx")
        self.assertEqual(ra, 1)
        self.assertEqual(rz, 2)

    @skip_py2
    def test_dict_as_item_in_list(self):
        @njit
        def foo():
            l = List.empty_list(Dict.empty(int32, int32))
            d = Dict.empty(int32, int32)
            d[0] = 1
            # This increments the refcount for d
            l.append(d)
            return get_refcount(d)

        c = foo()
        self.assertEqual(2, c)

    @skip_py2
    def test_dict_as_item_in_list_multi_refcount(self):
        @njit
        def foo():
            l = List.empty_list(Dict.empty(int32, int32))
            d = Dict.empty(int32, int32)
            d[0] = 1
            # This increments the refcount for d, twice
            l.append(d)
            l.append(d)
            return get_refcount(d)

        c = foo()
        self.assertEqual(3, c)

    @skip_py2
    def test_list_as_value_in_dict(self):
        @njit
        def foo():
            d = Dict.empty(int32, List.empty_list(int32))
            l = List.empty_list(int32)
            l.append(0)
            # This increments the refcount for l
            d[0] = l
            return get_refcount(l)

        c = foo()
        self.assertEqual(2, c)

    @skip_py2
    def test_list_as_item_in_list(self):
        nested_type = types.ListType(types.int32)
        @njit
        def foo():
            la = List.empty_list(nested_type)
            lb = List.empty_list(types.int32)
            lb.append(1)
            la.append(lb)
            return la

        expected = foo.py_func()
        got = foo()
        self.assertEqual(expected, got)

    @skip_py2
    def test_array_as_item_in_list(self):
        nested_type = types.Array(types.float64, 1, 'C')
        @njit
        def foo():
            l = List.empty_list(nested_type)
            a = np.zeros((1,))
            l.append(a)
            return l

        expected = foo.py_func()
        got = foo()
        # Need to compare the nested arrays
        self.assertTrue(np.all(expected[0] == got[0]))
