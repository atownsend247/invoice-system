from invoice_system.paths import DEFAULT_STORAGE_DIR, StoragePaths


def test_default_base_dir_is_storage():
    assert StoragePaths().base_dir.name == DEFAULT_STORAGE_DIR


def test_derives_every_path_under_the_base_dir(tmp_path):
    paths = StoragePaths(tmp_path / "my-storage")

    assert paths.domain_db_path == tmp_path / "my-storage" / "db" / "invoice_system.db"
    assert paths.auth_db_path == tmp_path / "my-storage" / "db" / "auth.db"
    assert paths.attachments_dir == tmp_path / "my-storage" / "attachments"
    assert paths.logs_dir == tmp_path / "my-storage" / "logs"


def test_domain_and_auth_db_share_one_db_subdirectory(tmp_path):
    paths = StoragePaths(tmp_path / "my-storage")
    assert paths.domain_db_path.parent == paths.auth_db_path.parent == paths.db_dir


def test_ensure_db_dir_creates_the_db_subdirectory(tmp_path):
    paths = StoragePaths(tmp_path / "my-storage")
    assert not paths.db_dir.exists()

    paths.ensure_db_dir()

    assert paths.db_dir.is_dir()


def test_ensure_db_dir_does_not_create_attachments_or_logs(tmp_path):
    # Those are created lazily elsewhere (AttachmentStore.save() on first
    # upload) or not at all yet (logs_dir is reserved for future use) -
    # ensure_db_dir() only ever needs to satisfy sqlite3.connect()/
    # SqliteAuthStore.open(), which require their own parent directory to
    # already exist.
    paths = StoragePaths(tmp_path / "my-storage")
    paths.ensure_db_dir()

    assert not paths.attachments_dir.exists()
    assert not paths.logs_dir.exists()


def test_ensure_db_dir_is_idempotent(tmp_path):
    paths = StoragePaths(tmp_path / "my-storage")
    paths.ensure_db_dir()
    paths.ensure_db_dir()  # must not raise
    assert paths.db_dir.is_dir()
