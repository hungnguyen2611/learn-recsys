from argparse import ArgumentParser

import numpy as np
import pytorch_lightning as pl
import torch
import torch.nn as nn
import torch.nn.functional as F
from pytorch_lightning.loggers import WandbLogger

from lit_data import LitDataModule
from lit_model import LitModel
from ml100k import ML100K


class MatrixFactorization(nn.Module):
    def __init__(self, embedding_dims, num_users, num_items, 
                 sparse=False, **kwargs):
        super().__init__()
        self.sparse = sparse
        
        self.user_embedding = nn.Embedding(num_users, embedding_dims, sparse=sparse)
        self.user_bias = nn.Embedding(num_users, 1, sparse=sparse)
        
        self.item_embedding = nn.Embedding(num_items, embedding_dims, sparse=sparse)
        self.item_bias = nn.Embedding(num_items, 1, sparse=sparse) 

        for param in self.parameters():
            nn.init.normal_(param, std=0.01)   

    def forward(self, user_id, item_id):
        Q = self.user_embedding(user_id)
        bq = self.user_bias(user_id).flatten()

        I = self.item_embedding(item_id)
        bi = self.item_bias(item_id).flatten()

        return (Q*I).sum(-1) + bq + bi


class LitMF(LitModel):
    def get_loss(self, pred_ratings, batch):
        return F.mse_loss(pred_ratings, batch[-1])

    def update_metric(self, m_outputs, batch, partition):
        _, _, gt = batch
        if partition == 'train':
            self.train_rmse.update(m_outputs, gt)
        else:
            self.valid_rmse.update(m_outputs, gt)

    def forward(self, batch):
        user_ids, item_ids, _ = batch
        return self.model(user_ids, item_ids)
        


def main(args):

    data = LitDataModule(ML100K(), batch_size=args.batch_size, num_workers=24)
    data.setup()
    model = LitMF(MatrixFactorization, sparse=False, 
        num_users=data.num_users, num_items=data.num_items,
        embedding_dims=args.embedding_dims)
    
    # wandb_logger = WandbLogger(project="proj_dummy")
    wandb_logger = WandbLogger(project="proj_recsys")
    trainer = pl.Trainer.from_argparse_args(
        args,
        devices=2,
        accelerator="gpu",
        strategy="ddp",
        max_epochs=30,
        logger=wandb_logger)

    train_dataloader = data.train_dataloader()
    valid_dataloader = data.val_dataloader()
    trainer.fit(model=model, train_dataloaders=train_dataloader, val_dataloaders=valid_dataloader)



if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--embedding_dims", type=int, default=30)
    parser.add_argument("--batch_size", type=int, default=512)
    pl.Trainer.add_argparse_args(parser)
    args = parser.parse_args()
    main(args)
