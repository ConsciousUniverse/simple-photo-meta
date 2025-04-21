from setuptools import setup, find_packages

setup(
    name="simple-photo-meta",
    version="0.1.0",
    description="A GUI tool for editing IPTC tags in images",
    author="Dan Bright",
    packages=find_packages(),
    install_requires=[
        "PySide6",
        "Pillow",
    ],
    entry_points={
        "gui_scripts": ["simple-photo-meta=simple_photo_meta.main:main"],
        "console_scripts": ["simple-photo-meta=simple_photo_meta.main:main"],
    },
    include_package_data=True,
    license="GPLv3",
)
