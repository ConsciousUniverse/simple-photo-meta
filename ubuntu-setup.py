from setuptools import setup, find_packages
from pybind11.setup_helpers import Pybind11Extension, build_ext

setup(
    name="simple-photo-meta",
    version="0.1",
    description="A GUI tool for editing IPTC tags in images",
    author="Dan Bright",
    packages=find_packages(),
    install_requires=[
        "PySide6",
        "Pillow",
        "pybind11>=2.6",
        "pillow-heif"
    ],
    setup_requires=["pybind11>=2.6"],
    ext_modules=[
        Pybind11Extension(
            "simple_photo_meta.exiv2bind",
            ["simple_photo_meta/exiv2_bindings.cpp",
             "simple_photo_meta/inih/INIReader.cpp",
             "simple_photo_meta/inih/ini_parser.cpp",
             ],
            include_dirs=[
                "/usr/local/include",
                "simple_photo_meta/inih",
            ],
            extra_compile_args=["-fPIC"],
            extra_link_args=[
                "-lexiv2",
                "-lbrotlicommon",
                "-lbrotlidec",
                "-lz",
            ],
            language="c++",
            cxx_std=17,
        ),
    ],
    cmdclass={"build_ext": build_ext},
    entry_points={"gui_scripts": ["simple-photo-meta=simple_photo_meta.main:main"]},
    include_package_data=True,
    license="GPLv3",
)
