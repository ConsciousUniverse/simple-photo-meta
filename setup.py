from setuptools import setup, find_packages
from pybind11.setup_helpers import Pybind11Extension, build_ext

setup(
    name="simple-photo-meta",
    version="0.1.0",
    description="A GUI tool for editing IPTC tags in images",
    author="Dan Bright",
    packages=find_packages(),
    install_requires=[
        "PySide6",
        "Pillow",
        "pybind11>=2.6",
    ],
    setup_requires=["pybind11>=2.6"],
    ext_modules=[
        Pybind11Extension(
            "simple_photo_meta.exiv2bind",
            ["simple_photo_meta/exiv2_bindings.cpp"],
            include_dirs=[
                # adjust for platform:
                "/opt/homebrew/include",  # macOS on Apple Silicon
                "/usr/local/include",  # macOS Intel / other
            ],
            libraries=["exiv2"],
            library_dirs=[
                "/opt/homebrew/lib",
                "/usr/local/lib",
            ],
            language="c++",
            extra_compile_args=["-std=c++17"],
        ),
    ],
    cmdclass={"build_ext": build_ext},
    entry_points={"gui_scripts": ["simple-photo-meta=simple_photo_meta.main:main"]},
    include_package_data=True,
    license="GPLv3",
)
