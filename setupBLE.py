from cx_Freeze import setup, Executable
import sys

# Include additional files and folders
buildOptions = dict(
    packages=["bleak", "asyncio", "serial", "serial.tools", "serial.tools.list_ports", "requests", "filelock", "websockets", "google.protobuf", "paramiko"],
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
        "calendar",
        "email",
        "mailbox",
        "imaplib",
        "poplib",
        "smtplib",
        "smtpd",
        "telnetlib",
        "socketserver",
        "http.server",
        "xmlrpc",
        "webbrowser",
        "wsgiref",
        "xdrlib",
        "plistlib",
        "binascii",
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
        # Image processing (keep PIL if needed)
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
        ('dwarf_ble_connect/','./dwarf_ble_connect'),
    ],
    # Optimize bytecode
    optimize=1,
    # Include MSVC runtime (Windows only)
    include_msvcr=True,
    # Compress packages to reduce size
    zip_include_packages=["*"],
    zip_exclude_packages=[]
)

# Define the base for a GUI application
base = 'Win32GUI' if sys.platform=='win32' else None
# Setup function
setup(
    name="Dwarfium BLE CONNECT",
    version="1.0",
    description="Dwarfium BLE CONNECT",
    options = dict(build_exe = buildOptions),
    executables=[Executable("connect_bluetooth.py")]
)
