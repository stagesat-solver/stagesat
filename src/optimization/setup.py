from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy as np

extensions = [
    Extension(
        "mcmc_cython",
        ["mcmc.pyx"],
        include_dirs=[np.get_include()],
        extra_compile_args=["-O3", "-march=native"],
        extra_link_args=[],
    )
]

setup(
    name="mcmc_cython",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            'language_level': "3",
            'boundscheck': False,
            'wraparound': False,
            'cdivision': True,
            'nonecheck': False,
        },
        annotate=True  # Creates HTML file showing C interaction
    ),
    include_dirs=[np.get_include()],
)