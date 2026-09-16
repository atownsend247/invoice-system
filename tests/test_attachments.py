from invoice_system.attachments import AttachmentStore


def test_save_then_read_round_trips_bytes(tmp_path):
    store = AttachmentStore(tmp_path / "attachments")
    store.save("abc123", b"%PDF-1.4 fake receipt bytes")
    assert store.read("abc123") == b"%PDF-1.4 fake receipt bytes"


def test_save_creates_the_base_directory_if_missing(tmp_path):
    base_dir = tmp_path / "does" / "not" / "exist" / "yet"
    store = AttachmentStore(base_dir)
    store.save("abc123", b"data")
    assert base_dir.exists()


def test_save_overwrites_an_existing_attachment_with_the_same_id(tmp_path):
    store = AttachmentStore(tmp_path / "attachments")
    store.save("abc123", b"first")
    store.save("abc123", b"second")
    assert store.read("abc123") == b"second"


def test_delete_removes_the_file(tmp_path):
    store = AttachmentStore(tmp_path / "attachments")
    store.save("abc123", b"data")
    store.delete("abc123")
    assert not (tmp_path / "attachments" / "abc123.pdf").exists()


def test_delete_of_a_missing_attachment_does_not_raise(tmp_path):
    store = AttachmentStore(tmp_path / "attachments")
    store.delete("never-saved")  # no-op, not an error - see AttachmentStore.delete
