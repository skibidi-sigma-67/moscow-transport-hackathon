import csv

from fastapi import UploadFile

from commons.contracts.v1.api.reference import DeviceMappingDto

from .repository import DeviceRepository


class DeviceService:
    def __init__(self, repository: DeviceRepository) -> None:
        self.repository = repository

    async def get_tr_id(self, unit_id: int) -> int | None:
        mapping = await self.repository.get_by_unit_id(unit_id)
        if mapping:
            return mapping.tr_id
        return None

    async def register_device(self, unit_id: int, tr_id: int) -> DeviceMappingDto:
        mapping = await self.repository.get_by_unit_id(unit_id)
        if not mapping:
            mapping = await self.repository.create(unit_id=unit_id, tr_id=tr_id)

        return DeviceMappingDto.model_validate(mapping)

    async def upload_devices_csv(self, file: UploadFile) -> int:
        content = await file.read()
        decoded_content = content.decode("utf-8").splitlines()
        reader = csv.DictReader(decoded_content, delimiter=",")

        unique_pairs = {}
        for row in reader:
            try:
                unit_id = int(row["unit_id"])
                tr_id = int(row["tr_id"])
                unique_pairs[unit_id] = tr_id
            except KeyError, ValueError:
                continue

        mappings = [{"unit_id": u, "tr_id": t} for u, t in unique_pairs.items()]

        total_inserted = 0
        chunk_size = 5000
        for i in range(0, len(mappings), chunk_size):
            chunk = mappings[i : i + chunk_size]
            count = await self.repository.bulk_create_if_not_exists(chunk)
            total_inserted += count

        return total_inserted
