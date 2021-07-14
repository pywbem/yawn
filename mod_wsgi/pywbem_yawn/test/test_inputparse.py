import unittest
import pywbem
from pywbem_yawn.inputparse import iname_str2pywbem

props = pywbem.NocaseDict({
    "Uint16Property" : { 'name':'Uint16Property', 'type':'uint16'
                       , 'is_key':True },
    "StringProperty" : { 'name':'StringProperty', 'type':'string'
                       , 'is_key':True },
    "BooleanProperty": { 'name':'BooleanProperty', 'type':'boolean'
                       , 'is_key':True },
    "Sint32Property" : { 'name':'Sint32Property', 'type':'sint32'
                       , 'is_key':True } })

class InputParseTest(unittest.TestCase):

    def test_iname_str2pywbem_correct_path1(self):
        path = iname_str2pywbem(props,
                """root/cimv2:LMI_YawnTest.StringProperty="short string","""
                """Uint16Property=10,BooleanProperty=TRUE""")
        self.assertIsInstance(path, pywbem.CIMInstanceName)
        self.assertEqual("root/cimv2", path.namespace)
        self.assertEqual("LMI_YawnTest", path.classname)
        self.assertIsInstance(path.keybindings, (dict, pywbem.NocaseDict))
        self.assertEqual(3, len(path.keybindings))
        self.assertIn("StringProperty", path)
        self.assertIn("Uint16Property", path)
        self.assertIn("BooleanProperty", path)
        self.assertEqual("short string", path["StringProperty"])
        self.assertIsInstance(path['Uint16Property'], pywbem.Uint16)
        self.assertEqual(pywbem.Uint16(10), path['Uint16Property'])
        self.assertEqual(True, path['BooleanProperty'])

    def test_iname_str2pywbem_correct_path2(self):
        path = iname_str2pywbem(props,
                """LMI_YawnTest.StringProperty="short \\ \\"\\\\ string\\"","""
                """Sint32Property=-10,BooleanProperty=FALSE""")
        self.assertIsInstance(path, pywbem.CIMInstanceName)
        self.assertIs(None, path.namespace)
        self.assertEqual("LMI_YawnTest", path.classname)
        self.assertIsInstance(path.keybindings, (dict, pywbem.NocaseDict))
        self.assertEqual(3, len(path.keybindings))
        self.assertIn("StringProperty", path)
        self.assertIn("Sint32Property", path)
        self.assertIn("BooleanProperty", path)
        self.assertEqual('short  "\\ string"', path["StringProperty"])
        self.assertIsInstance(path['Sint32Property'], pywbem.Sint32)
        self.assertEqual(pywbem.Sint32(-10), path['Sint32Property'])
        self.assertEqual(False, path['BooleanProperty'])

    def test_iname_str2pywbem_correct_path3(self):
        path = iname_str2pywbem(props,
                'AnyClass.StringProperty="short , \\"= string"')
        self.assertIsInstance(path, pywbem.CIMInstanceName)
        self.assertIs(None, path.namespace)
        self.assertEqual("AnyClass", path.classname)
        self.assertIsInstance(path.keybindings, (dict, pywbem.NocaseDict))
        self.assertEqual(1, len(path.keybindings))
        self.assertIn("StringProperty", path)
        self.assertEqual('short , "= string', path["StringProperty"])

    def test_iname_str2pywbem_correct_path4(self):
        path = iname_str2pywbem(props,
                """AnyClass.Uint16Property=0""")
        self.assertIsInstance(path, pywbem.CIMInstanceName)
        self.assertIs(None, path.namespace)
        self.assertEqual("AnyClass", path.classname)
        self.assertIsInstance(path.keybindings, (dict, pywbem.NocaseDict))
        self.assertEqual(1, len(path.keybindings))
        self.assertIn("Uint16Property", path)
        self.assertEqual(0, path["Uint16property"])

    def test_iname_str2pywbem_invalid_path(self):
        self.assertRaises(ValueError, iname_str2pywbem, props,
                """root/cimv2:LMI_YawnTest""")
        self.assertRaises(ValueError, iname_str2pywbem, props,
                """LMI_YawnTest,Uint16Property=10""")
        self.assertRaises(ValueError, iname_str2pywbem, props,
                'Uint16Property=10.StringProperty="abc"')
        self.assertRaises(ValueError, iname_str2pywbem, props,
                'Uint16Property=10,StringProperty="abc')
        self.assertRaises(ValueError, iname_str2pywbem, props,
                'Uint16Property=10,StringProperty=abc"')
        self.assertRaises(ValueError, iname_str2pywbem, props,
                'Uint16Property=10,StringProperty="abc')
        self.assertRaises(ValueError, iname_str2pywbem, props,
                'Uint16Property="10,StringProperty=abc"')
        self.assertRaises(ValueError, iname_str2pywbem, props,
                'Uint16Property=10,,StringProperty="abc"')
        self.assertRaises(ValueError, iname_str2pywbem, props, '')

if __name__ == '__main__':
    unittest.main()
