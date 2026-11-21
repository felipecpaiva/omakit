import unittest

from omakit import uinput


class UinputTest(unittest.TestCase):
    def test_codes(self):
        self.assertEqual(uinput.codes("Ctrl+Alt+Left"), [29, 56, 105])
        self.assertEqual([uinput.KEYS[k] for k in "1290az"], [2, 3, 10, 11, 30, 44])
        self.assertEqual((uinput.KEYS["f1"], uinput.KEYS["f10"], uinput.KEYS["f12"]), (59, 68, 88))
        with self.assertRaises(KeyError):
            uinput.codes("ctrl+nosuchkey")

    def test_codes_are_unique_and_cover_the_siblings(self):
        self.assertEqual(len(set(uinput.KEYS.values())), len(uinput.KEYS))
        siblings = ("ctrl alt shift super left right up down return backspace tab escape delete grave ralt space minus "
                    "bracketleft bracketright f9 f10 f11 f12 " + " ".join("abcdefghijklmnopqrstuvwxyz0123456789"))
        for k in siblings.split():
            self.assertIn(k, uinput.KEYS)

    def test_nothing_opened_until_entered(self):
        uinput.Keyboard(); uinput.Mouse(name="x")
