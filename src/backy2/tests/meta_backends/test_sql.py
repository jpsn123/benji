from unittest import TestCase

from backy2.tests.testcase import BackendTestCase


class test_sql(BackendTestCase, TestCase):

    CONFIG = """
        configurationVersion: '0.1'
        logFile: /dev/stderr
        lockDirectory: {testpath}/lock
        hashFunction: blake2b,digest_size=32
        metaBackend: 
          type: sql
          sql:
            engine: sqlite:///{testpath}/backy.sqlite
        """

    def test_version(self):
            version_uid = self.meta_backend.set_version('backup-name',
                                          'snapshot-name',
                                          4,
                                          4 * 1024 * 4096,
                                          False)
            self.meta_backend._commit()

            version = self.meta_backend.get_version(version_uid)
            self.assertEqual('backup-name', version.name)
            self.assertEqual('snapshot-name', version.snapshot_name)
            self.assertEqual(4, version.size)
            self.assertEqual(4 * 1024 * 4096, version.size_bytes)
            self.assertFalse(version.valid)
            self.assertFalse(version.protected)

            self.meta_backend.set_version_valid(version_uid)
            self.meta_backend._commit()
            version = self.meta_backend.get_version(version_uid)
            self.assertTrue(version.valid)

            self.meta_backend.set_version_invalid(version_uid)
            self.meta_backend._commit()
            version = self.meta_backend.get_version(version_uid)
            self.assertFalse(version.valid)

            self.meta_backend.protect_version(version_uid)
            self.meta_backend._commit()
            version = self.meta_backend.get_version(version_uid)
            self.assertTrue(version.protected)

            self.meta_backend.unprotect_version(version_uid)
            self.meta_backend._commit()
            version = self.meta_backend.get_version(version_uid)
            self.assertFalse(version.protected)

            self.meta_backend.add_tag(version_uid, 'tag-123')
            self.meta_backend._commit()
            version = self.meta_backend.get_version(version_uid)
            self.assertEqual(1, len(version.tags))
            self.assertIn(version_uid, map(lambda tag: tag.version_uid, version.tags))
            self.assertIn('tag-123', map(lambda tag: tag.name, version.tags))

            self.meta_backend.remove_tag(version_uid, 'tag-123')
            self.meta_backend._commit()
            version = self.meta_backend.get_version(version_uid)
            self.assertEqual(0, len(version.tags))

            version_uids = {}
            for _ in range(256):
                version_uid = self.meta_backend.set_version('backup-name',
                                                            'snapshot-name',
                                                            4,
                                                            4 * 1024 * 4096,
                                                            False)
                version = self.meta_backend.get_version(version_uid)
                self.assertNotIn(version.uid, version_uids)
                version_uids[version.uid] = True


    def test_block(self):
        version_uid = self.meta_backend.set_version('name-' + self.random_string(12),
                                      'snapshot-name-' + self.random_string(12),
                                      4,
                                      4 * 1024 * 4096,
                                      False)
        self.meta_backend._commit()

        checksums = []
        uids = []
        num_blocks = 256
        for id in range(num_blocks):
            checksums.append(self.random_hex(64))
            uids.append(self.random_string(32))
            self.meta_backend.set_block(
                id,
                version_uid,
                uids[id],
                checksums[id],
                1024 * 4096,
                True,
                _commit=False,
                _upsert=False)
        self.meta_backend._commit()

        for id, checksum in enumerate(checksums):
            block = self.meta_backend.get_block_by_checksum(checksum)
            self.assertEqual(id, block.id)
            self.assertEqual(version_uid, block.version_uid)
            self.assertEqual(uids[id], block.uid)
            self.assertEqual(checksum, block.checksum)
            self.assertEqual(1024 * 4096, block.size)
            self.assertTrue(block.valid)

        for id, uid in enumerate(uids):
            block = self.meta_backend.get_block(uid)
            self.assertEqual(id, block.id)
            self.assertEqual(version_uid, block.version_uid)
            self.assertEqual(uid, block.uid)
            self.assertEqual(checksums[id], block.checksum)
            self.assertEqual(1024 * 4096, block.size)
            self.assertTrue(block.valid)

        blocks = self.meta_backend.get_blocks_by_version(version_uid)
        self.assertEqual(num_blocks, len(blocks))
        for id, block in enumerate(blocks):
            self.assertEqual(id, block.id)
            self.assertEqual(version_uid, block.version_uid)
            self.assertEqual(uids[id], block.uid)
            self.assertEqual(checksums[id], block.checksum)
            self.assertEqual(1024 * 4096, block.size)
            self.assertTrue(block.valid)

        for id, block in enumerate(blocks):
            dereferenced_block = block.deref()
            self.assertEqual(id, dereferenced_block.id)
            self.assertEqual(version_uid, dereferenced_block.version_uid)
            self.assertEqual(uids[id], dereferenced_block.uid)
            self.assertEqual(checksums[id], dereferenced_block.checksum)
            self.assertEqual(1024 * 4096, dereferenced_block.size)
            self.assertTrue(dereferenced_block.valid)

        uids_all = self.meta_backend.get_all_block_uids()
        for uid in uids_all:
            self.assertIn(uid, uids)
        self.assertEqual(num_blocks, len(uids_all))

        self.meta_backend.rm_version(version_uid)
        self.meta_backend._commit()
        blocks = self.meta_backend.get_blocks_by_version(version_uid)
        self.assertEqual(0, len(blocks))

        count = 0
        for uids_deleted in self.meta_backend.get_delete_candidates(-1):
            for uid in uids_deleted:
                self.assertIn(uid, uids)
                count += 1
        self.assertEqual(num_blocks, count)
