import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_cross_build():
    windows_profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        """)
    rpi_profile = textwrap.dedent("""
        [settings]
        os=Linux
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        arch=armv8
        build_type=Release
        """)

    client = TestClient(path_with_spaces=False)

    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                "rpi": rpi_profile,
                 "windows": windows_profile})
    client.run("install . --profile:build=windows --profile:host=rpi")
    toolchain = client.load("conan_toolchain.cmake")

    assert "set(CMAKE_SYSTEM_NAME Linux)" in toolchain
    assert "set(CMAKE_SYSTEM_PROCESSOR armv8)" in toolchain


def test_cross_build_user_toolchain():
    # When a user_toolchain is defined in [conf], CMakeToolchain will not generate anything
    # for cross-build
    windows_profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        """)
    rpi_profile = textwrap.dedent("""
        [settings]
        os=Linux
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        arch=armv8
        build_type=Release
        [conf]
        tools.cmake.cmaketoolchain:user_toolchain=rpi_toolchain.cmake
        """)

    client = TestClient(path_with_spaces=False)

    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                "rpi": rpi_profile,
                 "windows": windows_profile})
    client.run("install . --profile:build=windows --profile:host=rpi")
    toolchain = client.load("conan_toolchain.cmake")

    assert "CMAKE_SYSTEM_NAME " not in toolchain
    assert "CMAKE_SYSTEM_PROCESSOR" not in toolchain


def test_no_cross_build():
    windows_profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        build_type=Release
        """)

    client = TestClient(path_with_spaces=False)

    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                 "windows": windows_profile})
    client.run("install . --profile:build=windows --profile:host=windows")
    toolchain = client.load("conan_toolchain.cmake")

    assert "CMAKE_SYSTEM_NAME " not in toolchain
    assert "CMAKE_SYSTEM_PROCESSOR" not in toolchain


def test_cross_arch():
    # Compiling to 32bits in an architecture that runs is not full cross-compiling
    build_profile = textwrap.dedent("""
        [settings]
        os=Linux
        arch=x86_64
        """)
    profile_arm = textwrap.dedent("""
        [settings]
        os=Linux
        arch=armv8
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        build_type=Release
        """)

    client = TestClient(path_with_spaces=False)

    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                "linux64": build_profile,
                 "linuxarm": profile_arm})
    client.run("install . --profile:build=linux64 --profile:host=linuxarm")
    toolchain = client.load("conan_toolchain.cmake")

    assert "set(CMAKE_SYSTEM_NAME Linux)" in toolchain
    assert "set(CMAKE_SYSTEM_PROCESSOR armv8)" in toolchain


def test_no_cross_build_arch():
    # Compiling to 32bits in an architecture that runs is not full cross-compiling
    build_profile = textwrap.dedent("""
        [settings]
        os=Linux
        arch=x86_64
        """)
    profile_32 = textwrap.dedent("""
        [settings]
        os=Linux
        arch=x86
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        build_type=Release
        """)

    client = TestClient(path_with_spaces=False)

    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                "linux64": build_profile,
                 "linux32": profile_32})
    client.run("install . --profile:build=linux64 --profile:host=linux32")
    toolchain = client.load("conan_toolchain.cmake")

    assert "CMAKE_SYSTEM_NAME" not in toolchain
    assert "CMAKE_SYSTEM_PROCESSOR " not in toolchain


def test_cross_build_conf():
    windows_profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        """)
    rpi_profile = textwrap.dedent("""
        [settings]
        os=Linux
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        arch=armv8
        build_type=Release

        [conf]
        tools.cmake.cmaketoolchain:system_name = Custom
        tools.cmake.cmaketoolchain:system_version= 42
        tools.cmake.cmaketoolchain:system_processor = myarm
        """)

    client = TestClient(path_with_spaces=False)

    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                "rpi": rpi_profile,
                 "windows": windows_profile})
    client.run("install . --profile:build=windows --profile:host=rpi")
    toolchain = client.load("conan_toolchain.cmake")

    assert "set(CMAKE_SYSTEM_NAME Custom)" in toolchain
    assert "set(CMAKE_SYSTEM_VERSION 42)" in toolchain
    assert "set(CMAKE_SYSTEM_PROCESSOR myarm)" in toolchain
