import os
import unittest
from collections import OrderedDict

from parameterized.parameterized import parameterized

from conans.model.manifest import FileTreeManifest
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import EXPORT_SOURCES_TGZ_NAME, EXPORT_SRC_FOLDER, EXPORT_TGZ_NAME
from conans.test.utils.test_files import scan_folder
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer
from conans.util.files import load, md5sum, save

conanfile_py = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*.h", "*.cpp"
    def package(self):
        self.copy("*.h", "include")
"""


combined_conanfile = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports_sources = "*.h", "*.cpp"
    exports = "*.txt"
    def package(self):
        self.copy("*.h", "include")
        self.copy("data.txt", "docs")
"""


nested_conanfile = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports_sources = "src/*.h", "src/*.cpp"
    exports = "src/*.txt"
    def package(self):
        self.copy("*.h", "include")
        self.copy("*data.txt", "docs")
"""


overlap_conanfile = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports_sources = "src/*.h", "*.txt"
    exports = "src/*.txt", "*.h"
    def package(self):
        self.copy("*.h", "include")
        self.copy("*data.txt", "docs")
"""


class ExportsSourcesTest(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.other_server = TestServer()
        servers = OrderedDict([("default", self.server),
                               ("other", self.other_server)])
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")],
                                                    "other": [("lasote", "mypass")]})
        self.client = client
        self.ref = ConanFileReference.loads("Hello/0.1@lasote/testing")
        self.pref = PackageReference(self.ref, NO_SETTINGS_PACKAGE_ID)
        self.source_folder = self.client.cache.package_layout(self.ref).source()
        self.package_folder = self.client.cache.package_layout(self.ref).package(self.pref)
        self.export_folder = self.client.cache.package_layout(self.ref).export()
        self.export_sources_folder = self.client.cache.package_layout(self.ref).export_sources()

    def _check_source_folder(self, mode):
        """ Source folder MUST be always the same
        """
        expected_sources = ["hello.h"]
        if mode == "both":
            expected_sources.append("data.txt")
        if mode == "nested" or mode == "overlap":
            expected_sources = ["src/hello.h", "src/data.txt"]
        expected_sources = sorted(expected_sources)
        self.assertEqual(scan_folder(self.source_folder), expected_sources)

    def _check_package_folder(self, mode):
        """ Package folder must be always the same (might have tgz after upload)
        """
        if mode in ["exports", "exports_sources"]:
            expected_package = ["conaninfo.txt", "conanmanifest.txt", "include/hello.h"]
        if mode == "both":
            expected_package = ["conaninfo.txt", "conanmanifest.txt", "include/hello.h",
                                "docs/data.txt"]
        if mode == "nested" or mode == "overlap":
            expected_package = ["conaninfo.txt", "conanmanifest.txt", "include/src/hello.h",
                                "docs/src/data.txt"]

        self.assertEqual(scan_folder(self.package_folder), sorted(expected_package))

    def _check_server_folder(self, mode, server=None):
        if mode == "exports_sources":
            expected_server = [EXPORT_SOURCES_TGZ_NAME, 'conanfile.py', 'conanmanifest.txt']
        if mode == "exports":
            expected_server = [EXPORT_TGZ_NAME, 'conanfile.py', 'conanmanifest.txt']
        if mode == "both" or mode == "nested" or mode == "overlap":
            expected_server = [EXPORT_TGZ_NAME, EXPORT_SOURCES_TGZ_NAME, 'conanfile.py',
                               'conanmanifest.txt']

        server = server or self.server
        rev, _ = server.server_store.get_last_revision(self.ref)
        ref = self.ref.copy_with_rev(rev)
        self.assertEqual(scan_folder(server.server_store.export(ref)), expected_server)

    def _check_export_folder(self, mode, export_folder=None, export_src_folder=None):
        if mode == "exports_sources":
            expected_src_exports = ["hello.h"]
            expected_exports = ['conanfile.py', 'conanmanifest.txt']
        if mode == "exports":
            expected_src_exports = []
            expected_exports = ["hello.h", 'conanfile.py', 'conanmanifest.txt']
        if mode == "both":
            expected_src_exports = ["hello.h"]
            expected_exports = ['conanfile.py', 'conanmanifest.txt', "data.txt"]
        if mode == "nested":
            expected_src_exports = ["src/hello.h"]
            expected_exports = ["src/data.txt", 'conanfile.py', 'conanmanifest.txt']
        if mode == "overlap":
            expected_src_exports = ["src/hello.h", "src/data.txt"]
            expected_exports = ["src/data.txt", "src/hello.h", 'conanfile.py', 'conanmanifest.txt']

        self.assertEqual(scan_folder(export_folder or self.export_folder),
                         sorted(expected_exports))
        self.assertEqual(scan_folder(export_src_folder or self.export_sources_folder),
                         sorted(expected_src_exports))

    def _check_export_installed_folder(self, mode):
        """ Just installed, no EXPORT_SOURCES_DIR is present
        """
        if mode == "exports_sources":
            expected_exports = ['conanfile.py', 'conanmanifest.txt']
        if mode == "both":
            expected_exports = ['conanfile.py', 'conanmanifest.txt', "data.txt"]
        if mode == "exports":
            expected_exports = ['conanfile.py', 'conanmanifest.txt', "hello.h"]
        if mode == "nested":
            expected_exports = ['conanfile.py', 'conanmanifest.txt', "src/data.txt"]
        if mode == "overlap":
            expected_exports = ['conanfile.py', 'conanmanifest.txt', "src/data.txt", "src/hello.h"]

        self.assertEqual(scan_folder(self.export_folder), sorted(expected_exports))
        self.assertFalse(os.path.exists(self.export_sources_folder))

    def _check_export_uploaded_folder(self, mode, export_folder=None, export_src_folder=None):
        if mode == "exports_sources":
            expected_src_exports = ["hello.h"]
            expected_exports = ['conanfile.py', 'conanmanifest.txt']
        if mode == "exports":
            expected_src_exports = []
            expected_exports = ["hello.h", 'conanfile.py', 'conanmanifest.txt']
        if mode == "both":
            expected_src_exports = ["hello.h"]
            expected_exports = ['conanfile.py', 'conanmanifest.txt', "data.txt"]
        if mode == "nested":
            expected_src_exports = ["src/hello.h"]
            expected_exports = ["src/data.txt", 'conanfile.py', 'conanmanifest.txt']

        if mode == "overlap":
            expected_src_exports = ["src/hello.h", "src/data.txt"]
            expected_exports = ["src/data.txt", "src/hello.h", 'conanfile.py', 'conanmanifest.txt']

        export_folder = export_folder or self.export_folder
        self.assertEqual(scan_folder(export_folder), sorted(expected_exports))
        self.assertEqual(scan_folder(export_src_folder or self.export_sources_folder),
                         sorted(expected_src_exports))

    def _check_manifest(self, mode):
        manifest = load(os.path.join(self.client.current_folder,
                                     ".conan_manifests/Hello/0.1/lasote/testing/export/"
                                     "conanmanifest.txt"))

        if mode == "exports_sources":
            self.assertIn("%s/hello.h: 5d41402abc4b2a76b9719d911017c592" % EXPORT_SRC_FOLDER,
                          manifest.splitlines())
        elif mode == "exports":
            self.assertIn("hello.h: 5d41402abc4b2a76b9719d911017c592",
                          manifest.splitlines())
        elif mode == "both":
            self.assertIn("data.txt: 8d777f385d3dfec8815d20f7496026dc", manifest.splitlines())
            self.assertIn("%s/hello.h: 5d41402abc4b2a76b9719d911017c592" % EXPORT_SRC_FOLDER,
                          manifest.splitlines())
        elif mode == "nested":
            self.assertIn("src/data.txt: 8d777f385d3dfec8815d20f7496026dc",
                          manifest.splitlines())
            self.assertIn("%s/src/hello.h: 5d41402abc4b2a76b9719d911017c592" % EXPORT_SRC_FOLDER,
                          manifest.splitlines())
        else:
            assert mode == "overlap"
            self.assertIn("src/data.txt: 8d777f385d3dfec8815d20f7496026dc",
                          manifest.splitlines())
            self.assertIn("src/hello.h: 5d41402abc4b2a76b9719d911017c592",
                          manifest.splitlines())
            self.assertIn("%s/src/hello.h: 5d41402abc4b2a76b9719d911017c592" % EXPORT_SRC_FOLDER,
                          manifest.splitlines())
            self.assertIn("%s/src/data.txt: 8d777f385d3dfec8815d20f7496026dc" % EXPORT_SRC_FOLDER,
                          manifest.splitlines())

    def _create_code(self, mode):
        if mode == "exports":
            conanfile = conanfile_py
        elif mode == "exports_sources":
            conanfile = conanfile_py.replace("exports", "exports_sources")
        elif mode == "both":
            conanfile = combined_conanfile
        elif mode == "nested":
            conanfile = nested_conanfile
        elif mode == "overlap":
            conanfile = overlap_conanfile

        if mode in ["nested", "overlap"]:
            self.client.save({"conanfile.py": conanfile,
                              "src/hello.h": "hello",
                              "src/data.txt": "data"})
        else:
            self.client.save({"conanfile.py": conanfile,
                              "hello.h": "hello",
                              "data.txt": "data"})

    @parameterized.expand([("exports", ), ("exports_sources", ), ("both", ), ("nested", ),
                           ("overlap", )])
    def test_copy(self, mode):
        # https://github.com/conan-io/conan/issues/943
        self._create_code(mode)

        self.client.run("export . lasote/testing")
        self.client.run("install Hello/0.1@lasote/testing --build=missing")
        self.client.run("upload Hello/0.1@lasote/testing --all")
        self.client.run('remove Hello/0.1@lasote/testing -f')
        self.client.run("install Hello/0.1@lasote/testing")

        # new copied package data
        ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        source_folder = self.client.cache.package_layout(ref).source()
        export_folder = self.client.cache.package_layout(ref).export()

        self.client.run("copy Hello/0.1@lasote/testing lasote/stable")
        self._check_export_folder(mode, export_folder)

        self.client.run("upload Hello/0.1@lasote/stable")
        self.assertFalse(os.path.exists(source_folder))
        self._check_export_uploaded_folder(mode, export_folder)
        self._check_server_folder(mode)

    @parameterized.expand([("exports", ), ("exports_sources", ), ("both", ), ("nested", ),
                           ("overlap", )])
    def test_export(self, mode):
        self._create_code(mode)

        self.client.run("export . lasote/testing")
        self._check_export_folder(mode)

        # now build package
        self.client.run("install Hello/0.1@lasote/testing --build=missing")
        # Source folder and package should be exatly the same
        self._check_export_folder(mode)
        self._check_source_folder(mode)
        self._check_package_folder(mode)

        # upload to remote
        self.client.run("upload Hello/0.1@lasote/testing --all")
        self._check_export_uploaded_folder(mode)
        self._check_server_folder(mode)

        # remove local
        self.client.run('remove Hello/0.1@lasote/testing -f')
        self.assertFalse(os.path.exists(self.export_folder))

        # install from remote
        self.client.run("install Hello/0.1@lasote/testing")
        self.assertFalse(os.path.exists(self.source_folder))
        self._check_export_installed_folder(mode)
        self._check_package_folder(mode)

        # Manifests must work too!
        self.client.run("install Hello/0.1@lasote/testing --manifests")
        self.assertFalse(os.path.exists(self.source_folder))
        # The manifests retrieve the normal state, as it retrieves sources
        self._check_export_folder(mode)
        self._check_package_folder(mode)
        self._check_manifest(mode)

        # lets try to verify
        self.client.run('remove Hello/0.1@lasote/testing -f')
        self.assertFalse(os.path.exists(self.export_folder))
        self.client.run("install Hello/0.1@lasote/testing --verify")
        self.assertFalse(os.path.exists(self.source_folder))
        # The manifests retrieve the normal state, as it retrieves sources
        self._check_export_folder(mode)
        self._check_package_folder(mode)
        self._check_manifest(mode)

    @parameterized.expand([("exports", ), ("exports_sources", ), ("both", ), ("nested", ),
                           ("overlap", )])
    def test_export_upload(self, mode):
        self._create_code(mode)

        self.client.run("export . lasote/testing")

        self.client.run("upload Hello/0.1@lasote/testing")
        self.assertFalse(os.path.exists(self.source_folder))
        self._check_export_uploaded_folder(mode)
        self._check_server_folder(mode)

        # remove local
        self.client.run('remove Hello/0.1@lasote/testing -f')
        self.assertFalse(os.path.exists(self.export_folder))

        # install from remote
        self.client.run("install Hello/0.1@lasote/testing --build")
        self._check_export_folder(mode)
        self._check_source_folder(mode)
        self._check_package_folder(mode)

        # Manifests must work too!
        self.client.run("install Hello/0.1@lasote/testing --manifests")
        # The manifests retrieve the normal state, as it retrieves sources
        self._check_export_folder(mode)
        self._check_package_folder(mode)
        self._check_manifest(mode)

    @parameterized.expand([("exports", ), ("exports_sources", ), ("both", ), ("nested", ),
                           ("overlap", )])
    def test_reupload(self, mode):
        """ try to reupload to same and other remote
        """
        self._create_code(mode)

        self.client.run("export . lasote/testing")
        self.client.run("install Hello/0.1@lasote/testing --build=missing")
        self.client.run("upload Hello/0.1@lasote/testing --all")
        self.client.run('remove Hello/0.1@lasote/testing -f')
        self.client.run("install Hello/0.1@lasote/testing")

        # upload to remote again, the folder remains as installed
        self.client.run("upload Hello/0.1@lasote/testing --all")
        self._check_export_installed_folder(mode)
        self._check_server_folder(mode)

        self.client.run("upload Hello/0.1@lasote/testing --all -r=other")
        self._check_export_uploaded_folder(mode)
        self._check_server_folder(mode, self.other_server)

    @parameterized.expand([("exports", ), ("exports_sources", ), ("both", ), ("nested", ),
                           ("overlap", )])
    def test_update(self, mode):
        self._create_code(mode)

        self.client.run("export . lasote/testing")
        self.client.run("install Hello/0.1@lasote/testing --build=missing")
        self.client.run("upload Hello/0.1@lasote/testing --all")
        self.client.run('remove Hello/0.1@lasote/testing -f')
        self.client.run("install Hello/0.1@lasote/testing")

        # upload to remote again, the folder remains as installed
        self.client.run("install Hello/0.1@lasote/testing --update")
        self.assertIn("Hello/0.1@lasote/testing: Already installed!", self.client.out)
        self._check_export_installed_folder(mode)
