from ..services import dataset_service
from ..models.dataset import PairedDataset
from .common import dataset_ids,dataset_summary,require,require_dataset
def list_all(db):
 return [dataset_summary(db,require(db,PairedDataset,ident)) for ident in dataset_ids(db)]
def detail(db,ident):return dataset_summary(db,require_dataset(db,ident))
def create(db,body):return dataset_summary(db,dataset_service.create(db,body))
