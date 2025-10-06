"""
MORK_playground.py

A step-by-step playground showing 12+ MORK operations you can run against a local mork_server.

Prerequisites:
 - mork_server running and listening on http://127.0.0.1:8000
 - The Python `client.py` (your MORK client code) is in the same directory so we can `from client import MORK`.
 - A small CSV file named `test.csv` (sample content included below) in the same folder.

Sample `test.csv` contents (6 lines):
foo,1
foo,2
bar,1
bar,2
baz,3
baz,4

How to use:
 - Edit the `BASE_URL` if your server is not on 127.0.0.1:8000
 - Run this file with Python 3.10+: `python MORK_playground.py`
 - Each demo prints clear separators and the server responses; read the comments for explanations.

This is intentionally verbose so you can learn what each step does.
"""

import csv
import time
from client import MORK

BASE_URL = "http://127.0.0.1:8000"

# ---------- Helpers ----------

def safe_print(title, payload):
    print("\n" + "=" * 40)
    print(title)
    print("-" * 40)
    if payload is None:
        print("(None)")
    else:
        # If object has .data like requests-style response wrapper in the client, print that
        try:
            print(payload.data)
        except Exception:
            print(payload)
    print("=" * 40 + "\n")


# ---------- Demos ----------

def demo_1_connect_and_status():
    """1) Connect to the server and check that it accepts our status request."""
    print("Demo 1: connect and status")
    with MORK(base_url=BASE_URL) as server:
        # The client performs a GET /status/- during init; if we are here, connection succeeded.
        safe_print("Connected. Current download() of server:", server.download_())


def demo_2_upload_and_download():
    """2) Upload a few s-expr lines and download them back."""
    print("Demo 2: upload and download")
    with MORK(base_url=BASE_URL).and_clear() as server:
        server.upload_("(foo 1)\n(foo 2)\n(bar 3)")
        # download everything in this scope
        out = server.download_()
        safe_print("After upload, download() returns:", out)


def demo_3_csv_import_via_python():
    """3) Import CSV by converting rows to s-expr and upload (client has no csv_import method)."""
    print("Demo 3: csv -> upload_")
    with MORK(base_url=BASE_URL).and_clear() as server:
        rows = []
        with open("test.csv") as f:
            r = csv.reader(f)
            for row in r:
                # create expressions like (foo 1)
                rows.append(f"({row[0]} {row[1]})")
        server.upload_("\n".join(rows))
        safe_print("Uploaded CSV rows as s-expr; server.download():", server.download_())


def demo_4_transform_simple():
    """4) Apply a transform: change (foo $x) -> (baz $x). Use .block() to wait for completion."""
    print("Demo 4: transform (foo $x) -> (baz $x)")
    with MORK(base_url=BASE_URL).and_clear() as server:
        server.upload_("(foo 1)\n(foo 2)\n(bar 5)")
        # Request transform; pattern and template lists can have multiple items.
        t = server.transform(("(foo $x)",), ("(baz $x)",))
        # block() polls until transform is finished
        t.block()
        safe_print("After transform, download():", server.download_())


def demo_5_nested_workspaces_and_clear():
    """5) Show work_at() isolating data and .and_clear() to auto-clear at exit."""
    print("Demo 5: nested workspaces")
    with MORK(base_url=BASE_URL).and_clear() as server:
        server.upload_("(global 1)")
        with server.work_at("inner").and_clear() as inner:
            inner.upload_("(inner 1)")
            safe_print("Inner workspace download:", inner.download_())
            safe_print("Parent download (should not contain inner scope):", server.download_())
        # after exiting inner, inner was auto-cleared
        safe_print("After inner cleared, parent download():", server.download_())


def demo_6_explore_values_and_levels():
    """6) Use explore_() to examine values and traverse levels."""
    print("Demo 6: explore_")
    with MORK(base_url=BASE_URL).and_clear() as server:
        server.upload_("(animal cat)\n(animal dog)\n(color red)\n(color blue)")
        explorer = server.explore_()
        # explorer.dispatch() happens inside levels() iteration in the client; we print values per level
        for level_idx, level in enumerate(explorer.levels()):
            print(f"Level {level_idx} values:")
            for node in level:
                node.dispatch(server)
                print("  ", node.values())


def demo_7_exec_thread_and_transform_exec():
    """7) Run a small MM2-style exec flow: upload exec specs, transform them into a named thread, run it."""
    print("Demo 7: exec flow")
    with MORK(base_url=BASE_URL).and_clear() as server:
        # The server's exec/methods are meta — this is a canonical example from your original code
        server.upload_("(_exec 0 (, (data (foo $x))) (, (data (bar $x))))")
        # transform the generic _exec into a concrete named exec thread
        server.transform(("(_exec $priority $p $t)",), ("(exec (test $priority) $p $t)",)).block()
        # run the exec thread called 'test'
        server.exec(thread_id="test").listen()
        safe_print("After exec, server.download():", server.download_())


def demo_8_import_from_url_and_listen():
    """8) Import s-expressions from a remote URL (if server supports it) and listen to status events."""
    print("Demo 8: sexpr_import_ from URL")
    example_url = "https://raw.githubusercontent.com/trueagi-io/metta-examples/refs/heads/main/aunt-kg/simpsons.metta"
    with MORK(base_url=BASE_URL).and_clear() as server:
        # sexpr_import_ will return a Request object; calling .listen() waits for completion via SSE
        # (Note: this requires the server to support streaming status updates)
        try:
            server.sexpr_import_(example_url).listen()
            safe_print("Imported from URL; server.download():", server.download_())
        except Exception as e:
            print("Import from URL failed (server may not support remote import or network):", e)


def demo_9_export_to_file():
    """9) Export the current scope to a local file URI (server must support file:// or tmp writer)."""
    print("Demo 9: sexpr_export to file (if supported by server)")
    out_uri = "file:///tmp/mork_export.metta"
    with MORK(base_url=BASE_URL).and_clear() as server:
        server.upload_("(a 1)\n(b 2)")
        try:
            server.sexpr_export_(out_uri).block()
            print("Requested export to", out_uri)
        except Exception as e:
            print("Export request failed or not supported by server:", e)


def demo_10_clear_and_stop_server():
    """10) Demonstrate clear() and stop() commands.

    Note: stop() will instruct the mork_server to terminate; use with caution on a dev server.
    """
    print("Demo 10: clear() and stop() (stop commented out by default)")
    with MORK(base_url=BASE_URL) as server:
        server.upload_("(will be cleared)")
        safe_print("Before clear, download():", server.download_())
        server.clear().block()
        safe_print("After clear, download():", server.download_())
        # Stop the server only if you want to terminate it from this script:
        # server.stop()
        print("(Server stop call is commented out to avoid killing your running dev server.)")


def demo_11_history_and_inspect_requests():
    """11) Show the stored `history` list of Request objects created during the session."""
    print("Demo 11: request history")
    with MORK(base_url=BASE_URL) as server:
        server.upload_("(h 1)")
        server.download_()
        # history contains Request objects in order created
        for i, req in enumerate(server.history):
            print(i, type(req).__name__, str(req))


def demo_12_concurrent_playground_small_pool():
    """12) Example showing how you might run multiple isolated workspaces sequentially (simple loop).

    Note: Multiprocessing with the server is possible but can complicate logs and process ownership of server binary.
    This demo keeps it simple: create 4 isolated workspaces sequentially to show namespace isolation.
    """
    print("Demo 12: multiple isolated workspaces (sequential)")
    with MORK(base_url=BASE_URL) as server:
        for i in range(4):
            ns_name = f"play{i}"
            with server.work_at(ns_name).and_clear() as w:
                w.upload_(f"(in {i})\n(value {i * 10})")
                safe_print(f"workspace {ns_name} contents:", w.download_())
        safe_print("Parent scope (should not include inner playN items):", server.download_())


# ---------- Runner ----------

def run_all():
    demos = [
        demo_1_connect_and_status,
        demo_2_upload_and_download,
        demo_3_csv_import_via_python,
        demo_4_transform_simple,
        demo_5_nested_workspaces_and_clear,
        demo_6_explore_values_and_levels,
        demo_7_exec_thread_and_transform_exec,
        demo_8_import_from_url_and_listen,
        demo_9_export_to_file,
        demo_10_clear_and_stop_server,
        demo_11_history_and_inspect_requests,
        demo_12_concurrent_playground_small_pool,
    ]

    for demo in demos:
        try:
            demo()
        except Exception as e:
            print(f"Demo {demo.__name__} failed:", e)
        time.sleep(0.35)


if __name__ == "__main__":
    run_all()
