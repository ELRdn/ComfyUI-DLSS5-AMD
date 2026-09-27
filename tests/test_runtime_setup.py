"""Setup boundary tests use synthetic files; they do not execute a neural runtime.

Run independently of pytest: python -m unittest discover -s tests -p test_runtime_setup.py
"""
import copy
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.request
import zipfile

from amd_nr import runtime_setup as setup
from amd_nr.config import load_native_config
from amd_nr.errors import ConfigurationError


def digest(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def pe(dll=False):
    data = bytearray(512)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<H", data, 132, 0x8664)
    struct.pack_into("<H", data, 150, 0x2022 if dll else 0x22)
    struct.pack_into("<H", data, 152, 0x20B)
    return bytes(data)


class RuntimeSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lock = copy.deepcopy(setup.load_lock())
        self.payload = b"SYNTHETIC INSTALLER - NEVER EXECUTE"
        self.proxy = pe(dll=True) + b"synthetic runtime"
        self.weights = b"SYNTHETIC WEIGHTS - NO INFERENCE"
        self.lock["installer"].update(digest(self.payload))
        self.lock["proxy"].update(digest(self.proxy))
        self.lock["weights"].update(digest(self.weights))
        self.write_lock()
        self.cache = self.root / "local-build/runtime-downloads/v0.2.17/dlssnr_on_amd_setup.exe"
        self.model = self.root / "nvngx_dlssnr.dll"
        self.model.write_bytes(pe(dll=True))
        self.engine = self.root / "local-build/native/dlss5_video_native.exe"
        self.engine.parent.mkdir(parents=True)
        self.engine.write_bytes(pe())
        (self.engine.parent / "build-record.json").write_text(json.dumps({
            "expected_source_commit": self.lock["host_commit"], "engine_sha256": setup.sha256(self.engine)}))
        self.config = self.root / "config/backend.local.json"

    def write_lock(self):
        (self.root / "runtime.lock.json").write_text(json.dumps(self.lock), encoding="utf-8")

    def download(self, data=None):
        return setup.download_setup(self.root, opener=lambda *a, **kw: io.BytesIO(self.payload if data is None else data))

    def synthetic_installer(self, executable, directory):
        (directory / "dxgi.dll").write_bytes(self.proxy)
        (directory / "dlssnr_on_amd_weights.bin").write_bytes(self.weights)

    def install(self, **kwargs):
        self.download()
        runner = kwargs.pop("runner", self.synthetic_installer)
        model = kwargs.pop("model", self.model)
        with patch.object(setup.platform, "system", return_value="Windows"), \
             patch.object(setup, "file_version", return_value="310.8.0.0"), \
             patch.object(setup, "run_installer", side_effect=runner):
            return setup.install_runtime(model, root=self.root, hip_device="1",
                                         accept_runtime_license=True, **kwargs)

    def test_user_zip_import_installs_one_model_and_removes_temp_copy(self):
        archive = self.root / "owned-game-files.zip"
        with zipfile.ZipFile(archive, "w") as out:
            out.writestr("game/bin/nvngx_dlssnr.dll", self.model.read_bytes())
            out.writestr("game/readme.txt", "unrelated")
        with setup.model_from_zip(archive, root=self.root) as model:
            self.assertEqual(model.read_bytes(), self.model.read_bytes())
            record = self.install(model=model, enable_config=True)
        self.assertFalse(model.exists())
        self.assertTrue(Path(record["model"]["path"]).exists())
        self.assertEqual(load_native_config(self.config).hip_device, "1")
        self.assertEqual(archive.stat().st_size > 0, True)

    def test_zip_rejects_duplicates_unsafe_paths_and_size(self):
        archive = self.root / "bad.zip"
        for names in (("a/nvngx_dlssnr.dll", "b/nvngx_dlssnr.dll"),
                      ("../nvngx_dlssnr.dll",), ("nvngx_dlssnr.dll",)):
            with zipfile.ZipFile(archive, "w") as out:
                for name in names:
                    info = zipfile.ZipInfo(name)
                    if names == ("nvngx_dlssnr.dll",):
                        info.file_size = setup.MAX_MODEL_BYTES + 1
                    out.writestr(info, self.model.read_bytes())
            if names == ("nvngx_dlssnr.dll",):
                # Construct a ZIP entry that advertises an excessive expanded size.
                data = bytearray(archive.read_bytes())
                position = data.index(b"PK\x01\x02")
                struct.pack_into("<I", data, position + 24, setup.MAX_MODEL_BYTES + 1)
                archive.write_bytes(data)
            with self.assertRaises((ValueError, zipfile.BadZipFile)):
                with setup.model_from_zip(archive, root=self.root):
                    pass

    def test_download_is_verified_and_cached_without_network(self):
        self.assertEqual(self.download()["sha256"], digest(self.payload)["sha256"])
        with patch.object(urllib.request, "build_opener", side_effect=AssertionError("unexpected network")):
            self.assertEqual(setup.download_setup(self.root)["bytes"], len(self.payload))

    def test_wrong_download_never_becomes_executable(self):
        for data in (b"short", self.payload+b"oversize", b"x"*len(self.payload)):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.download(data)
            self.assertFalse(self.cache.exists())
            self.assertEqual(list(self.cache.parent.glob("*.partial")), [])

    def test_changed_cache_is_preserved_and_rejected(self):
        self.download()
        self.cache.write_bytes(b"changed")
        with self.assertRaises(ValueError):
            self.download()
        self.assertEqual(self.cache.read_bytes(), b"changed")

    def test_download_redirect_must_stay_on_https_release_hosts(self):
        handler = setup._ReleaseRedirect()
        request = urllib.request.Request(self.lock["installer"]["url"])
        for url in ("http://github.com/file", "https://example.com/file"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                handler.redirect_request(request, None, 302, "redirect", {}, url)

    def test_latest_runtime_cannot_silently_replace_baseline(self):
        self.lock["tag"] = "v0.4.0"
        self.write_lock()
        with self.assertRaises(ValueError):
            setup.load_lock(self.root)

    def test_model_must_be_correct_pe_and_version(self):
        with patch.object(setup, "file_version", return_value="310.8.0.0"):
            self.assertEqual(setup.inspect_model(self.model, self.lock)["file_version"], "310.8.0.0")
        with patch.object(setup, "file_version", return_value="310.7.0.0"), self.assertRaises(ValueError):
            setup.inspect_model(self.model, self.lock)
        self.model.write_bytes(b"not a DLL")
        with self.assertRaises(ValueError):
            setup.inspect_model(self.model, self.lock)

    def test_pe_header_rejects_x86_or_non_dll(self):
        data = bytearray(pe(dll=True))
        struct.pack_into("<H", data, 132, 0x14C)
        self.model.write_bytes(data)
        with self.assertRaises(ValueError):
            setup.pe_x64(self.model, dll=True)
        self.model.write_bytes(pe())
        with self.assertRaises(ValueError):
            setup.pe_x64(self.model, dll=True)

    def test_host_change_invalidates_build_record(self):
        self.engine.write_bytes(pe() + b"changed")
        with self.assertRaises(ValueError):
            setup.verify_engine(self.engine, self.lock)

    def test_license_and_existing_config_gate_precede_execution(self):
        with patch.object(setup.platform, "system", return_value="Windows"), \
             patch.object(setup, "run_installer") as run:
            with self.assertRaises(ValueError):
                setup.install_runtime(self.model, root=self.root, hip_device="1")
            self.config.parent.mkdir()
            self.config.write_text("existing settings")
            with self.assertRaises(FileExistsError):
                setup.install_runtime(self.model, root=self.root, hip_device="1", accept_runtime_license=True)
            run.assert_not_called()
        self.assertEqual(self.config.read_text(), "existing settings")

    def test_failed_setup_cannot_publish_config(self):
        def failed(*args):
            raise RuntimeError("setup failed")
        with self.assertRaises(RuntimeError):
            self.install(runner=failed)
        self.assertFalse(self.config.exists())

    def test_unexpected_generated_weights_cannot_publish_config(self):
        def bad(executable, directory):
            self.synthetic_installer(executable, directory)
            (directory / "dlssnr_on_amd_weights.bin").write_bytes(b"wrong")
        with self.assertRaises(ValueError):
            self.install(runner=bad)
        self.assertFalse(self.config.exists())

    def test_multiple_proxies_cannot_publish_config(self):
        def bad(executable, directory):
            self.synthetic_installer(executable, directory)
            (directory / "version.dll").write_bytes(self.proxy)
        with self.assertRaises(ValueError):
            self.install(runner=bad)
        self.assertFalse(self.config.exists())

    def test_disabled_config_and_source_files_are_preserved(self):
        before = self.model.read_bytes()
        record = self.install()
        self.assertFalse(record["neural_inference_tested"])
        self.assertFalse(record["config_enabled"])
        self.assertEqual(self.model.read_bytes(), before)
        with self.assertRaises(ConfigurationError):
            load_native_config(self.config)
        self.assertEqual(Path(record["artifacts"]["version.dll"]["path"]).read_bytes(), self.proxy)

    def test_opt_in_config_matches_real_bridge_schema(self):
        record = self.install(enable_config=True)
        config = load_native_config(self.config)
        config.verify()
        self.assertEqual(config.hip_device, "1")
        self.assertFalse(config.fast_isolated)
        self.assertFalse(record["neural_inference_tested"])

    def test_config_publication_never_overwrites(self):
        setup.write_new_json(self.config, {"original": True})
        with self.assertRaises(FileExistsError):
            setup.write_new_json(self.config, {"original": False})
        self.assertEqual(json.loads(self.config.read_text()), {"original": True})

    def test_installer_stdin_protocol_with_real_child(self):
        real_popen = subprocess.Popen
        marker = self.root / "protocol-fixture.exe"
        code = "import sys; assert sys.stdin.buffer.read() == b'y\\n\\n\\n\\n'; print('protocol received')"
        def launch(argv, **kwargs):
            return real_popen([sys.executable, "-c", code] if argv == [str(marker)] else argv, **kwargs)
        with patch.object(setup.subprocess, "Popen", side_effect=launch):
            setup.run_installer(marker, self.root, timeout=10)
        self.assertIn("protocol received", (self.root / "setup-output.log").read_text())

    def test_installer_timeout_stops_real_child(self):
        real_popen = subprocess.Popen
        marker = self.root / "timeout-fixture.exe"
        children = []
        def launch(argv, **kwargs):
            if argv == [str(marker)]:
                child = real_popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
                children.append(child)
                return child
            return real_popen(argv, **kwargs)
        with patch.object(setup.subprocess, "Popen", side_effect=launch):
            with self.assertRaises(subprocess.TimeoutExpired):
                setup.run_installer(marker, self.root, timeout=0.2)
        self.assertIsNotNone(children[0].poll())


if __name__ == "__main__":
    unittest.main()
