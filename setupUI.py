from cx_Freeze import setup, Executable
import sys

# Include additional files and folders
buildOptions = dict(
    packages=["bleak", "asyncio", "tkinter", "PIL", "serial", "requests"],
    excludes=[
        # Standard library exclusions
        "tkinter.test",
        "test",
        "unittest",
        "pdb",
        "pydoc",
        "doctest",
        "argparse",
        "optparse",
        "getopt",
        "gettext",
        "locale",
        "calendar",
        "email",
        "mailbox",
        "imaplib",
        "poplib",
        "smtplib",
        "smtpd",
        "telnetlib",
        "uuid",
        "socketserver",
        "http.server",
        "xmlrpc",
        "webbrowser",
        "wsgiref",
        "xdrlib",
        "plistlib",
        "binascii",
        "base64",
        "binhex",
        "uu",
        "quopri",
        "mailcap",
        "mailbox",
        "mhlib",
        "mimify",
        "multifile",
        "rfc822",
        "formatter",
        # Third party exclusions
        "numpy.testing",
        "numpy.tests",
        "PIL.tests",
        "PIL.test",
        "matplotlib.tests",
        "matplotlib.test",
        "scipy.test",
        "scipy.tests",
        "pandas.tests",
        "pandas.test",
        "setuptools",
        "pip",
        "distutils",
        "pkg_resources",
        # Development tools
        "pylint",
        "flake8",
        "black",
        "mypy",
        "pytest",
        "coverage",
        "sphinx",
        "jupyter",
        "notebook",
        "ipykernel",
        "IPython",
        # Database drivers (if not needed)
        "sqlite3",
        "psycopg2",
        "pymongo",
        "redis",
        # Web frameworks (if not needed)
        "django",
        "flask",
        "fastapi",
        "tornado",
        # Async libraries (keep only what you need)
        "aiohttp",
        "httpx",
        "trio",
        "curio",
        "uvloop",
        # Compression libraries (keep what you need)
        "lzma",
        "bz2",
        # Cryptography (if not needed)
        "cryptography",
        "pycryptodome",
        "hashlib",
        # Image processing (keep PIL)
        "opencv",
        "scikit-image",
        # Scientific computing (if not needed)
        "scipy",
        "sympy",
        "pandas",
        "numpy",
        # Machine learning (if not needed)
        "tensorflow",
        "torch",
        "sklearn",
        "xgboost",
        # Documentation and examples
        "examples",
        "docs",
        "doc",
        "tutorials",
        "demos"
    ],
    include_files=[
        ('dwarf_ble_connect/', './dwarf_ble_connect'),
        ('Install/', '.')
    ],
    # Optimize bytecode
    optimize=1,
    # Include MSVC runtime (Windows only)
    include_msvcr=True,
    # Compress packages to reduce size
    zip_include_packages=["*"],
    zip_exclude_packages=[],
    # Replace paths to make the build more portable
    replace_paths=[("*", "")],
    # Build constants for better optimization
    constants=[],
    # Don't create a zip file for the build
    create_zipfile=False
)

# Define the base for a GUI application
base = 'Win32GUI' if sys.platform == 'win32' else None

# Setup function
setup(
    name="Astro Dwarf Scheduler",
    version="1.7.0",
    description="Dwarf Astro Scheduler",
    options=dict(build_exe=buildOptions),
    executables=[
        Executable(
            "astro_dwarf_session_UI.py",
            base=base,
            icon="Install/astro_dwarf_session_UI.ico"
        )
    ]
)