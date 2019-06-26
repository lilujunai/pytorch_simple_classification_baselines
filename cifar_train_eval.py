import os
import time
import argparse
from datetime import datetime

import torch
import torch.optim as optim

import torchvision
from tensorboardX import SummaryWriter

from nets.cifar_vgg import *
from nets.cifar_resnet import *
from utils.preprocessing import *

# Training settings
parser = argparse.ArgumentParser(description='classification_baselines')

parser.add_argument('--root_dir', type=str, default='./')
parser.add_argument('--data_dir', type=str, default='./data')
parser.add_argument('--log_name', type=str, default='resnet20_baseline')
parser.add_argument('--pretrain', action='store_true', default=False)
parser.add_argument('--pretrain_dir', type=str, default='./ckpt/')

parser.add_argument('--lr', type=float, default=0.1)
parser.add_argument('--wd', type=float, default=5e-4)

parser.add_argument('--train_batch_size', type=int, default=128)
parser.add_argument('--test_batch_size', type=int, default=200)
parser.add_argument('--max_epochs', type=int, default=200)

parser.add_argument('--log_interval', type=int, default=10)
parser.add_argument('--use_gpu', type=str, default='0')
parser.add_argument('--num_workers', type=int, default=0)

cfg = parser.parse_args()

cfg.log_dir = os.path.join(cfg.root_dir, 'logs', cfg.log_name)
cfg.ckpt_dir = os.path.join(cfg.root_dir, 'ckpt', cfg.log_name)

os.makedirs(cfg.log_dir, exist_ok=True)
os.makedirs(cfg.ckpt_dir, exist_ok=True)

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"  # see issue #152
os.environ["CUDA_VISIBLE_DEVICES"] = cfg.use_gpu


def main():
  dataset = torchvision.datasets.CIFAR10

  # Data
  print('==> Preparing data..')
  trainset = dataset(root=cfg.data_dir, train=True, download=True,
                     transform=cifar_transform(is_training=True))
  train_loader = torch.utils.data.DataLoader(trainset,
                                             batch_size=cfg.train_batch_size,
                                             shuffle=True,
                                             num_workers=cfg.num_workers)

  testset = dataset(root=cfg.data_dir, train=False,
                    transform=cifar_transform(is_training=False))
  test_loader = torch.utils.data.DataLoader(testset,
                                            batch_size=cfg.test_batch_size,
                                            shuffle=False,
                                            num_workers=cfg.num_workers)

  print('==> Building model..')
  model = resnet20().cuda()

  optimizer = torch.optim.SGD(model.parameters(), lr=cfg.lr, momentum=0.9, weight_decay=cfg.wd)
  lr_schedulr = optim.lr_scheduler.StepLR(optimizer, 60, 0.1)
  criterion = torch.nn.CrossEntropyLoss()

  summary_writer = SummaryWriter(cfg.log_dir)

  # Training
  def train(epoch):
    print('\nEpoch: %d' % epoch)
    model.train()

    start_time = time.time()
    for batch_idx, (inputs, targets) in enumerate(train_loader):
      outputs = model(inputs.cuda())
      loss = criterion(outputs, targets.cuda())

      optimizer.zero_grad()
      loss.backward()
      optimizer.step()

      if batch_idx % cfg.log_interval == 0:
        step = len(train_loader) * epoch + batch_idx
        duration = time.time() - start_time

        print('%s epoch: %d step: %d cls_loss= %.5f (%d samples/sec)' %
              (datetime.now(), epoch, batch_idx, loss.item(),
               cfg.train_batch_size * cfg.log_interval / duration))

        start_time = time.time()
        summary_writer.add_scalar('cls_loss', loss.item(), step)
        summary_writer.add_scalar('learning rate', optimizer.param_groups[0]['lr'], step)

  def test(epoch):
    model.eval()
    correct = 0
    with torch.no_grad():
      for batch_idx, (inputs, targets) in enumerate(test_loader):
        outputs = model(inputs.cuda())
        _, predicted = torch.max(outputs.data, 1)
        correct += predicted.eq(targets.cuda().data).cpu().sum().item()

      acc = 100. * correct / len(test_loader.dataset)
      print('%s Precision@1 ==> %.2f%% \n' % (datetime.now(), acc))
      summary_writer.add_scalar('Precision@1', acc, global_step=epoch)
    return

  for epoch in range(cfg.max_epochs):
    lr_schedulr.step(epoch)
    train(epoch)
    test(epoch)
    torch.save(model.state_dict(), os.path.join(cfg.ckpt_dir, 'checkpoint.t7'))
    print('checkpoint saved to %s !' % os.path.join(cfg.ckpt_dir, 'checkpoint.t7'))

  summary_writer.close()


if __name__ == '__main__':
  main()
