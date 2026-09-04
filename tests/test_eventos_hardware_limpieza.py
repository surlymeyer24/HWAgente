"""Tests de limpieza TTL de eventos_hardware."""

from unittest.mock import MagicMock, patch


def test_limpiar_eventos_hardware_sin_docs():
    mock_db = MagicMock()
    mock_db.collection.return_value.where.return_value.limit.return_value.get.return_value = []

    with patch("src.database.firebase_client.db", mock_db):
        from src.database.firebase_client import limpiar_eventos_hardware_viejos
        limpiar_eventos_hardware_viejos(batch_size=50)

    mock_db.collection.assert_called_with("eventos_hardware")


def test_limpiar_eventos_hardware_elimina_batch():
    doc1 = MagicMock()
    doc1.reference = "ref1"
    doc2 = MagicMock()
    doc2.reference = "ref2"
    mock_batch = MagicMock()
    mock_db = MagicMock()
    mock_db.collection.return_value.where.return_value.limit.return_value.get.return_value = [doc1, doc2]
    mock_db.batch.return_value = mock_batch

    ran = []

    def _thread_ctor(target, daemon):
        ran.append(True)
        target()
        mock_thread = MagicMock()
        mock_thread.start = MagicMock()
        return mock_thread

    with patch("src.database.firebase_client.db", mock_db), \
         patch("src.database.firebase_client._ejecutar_con_reintento", side_effect=lambda fn: fn()), \
         patch("src.database.firebase_client.threading.Thread", side_effect=_thread_ctor):
        from src.database.firebase_client import limpiar_eventos_hardware_viejos
        limpiar_eventos_hardware_viejos(batch_size=100)

    assert ran
    assert mock_batch.delete.call_count == 2
    mock_batch.commit.assert_called_once()
