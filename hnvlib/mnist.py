"""MNIST 데이터셋으로 간단한 뉴럴 네트워크를 훈련하고 추론하는 코드입니다.
"""
from typing import Dict, List
import torch
from torch import Tensor, nn, optim
from torch.utils.data import Dataset, DataLoader
from torchvision import datasets
from torchvision.transforms import ToTensor
import pytorch_lightning as pl
from pytorch_lightning import Trainer
from torchmetrics import Accuracy


_Optimizer = torch.optim.Optimizer


class NeuralNetwork(nn.Module):
    """학습과 추론에 사용되는 간단한 뉴럴 네트워크입니다.
    """
    def __init__(self) -> None:
        super(NeuralNetwork, self).__init__()
        self.flatten = nn.Flatten()
        self.linear_relu_stack = nn.Sequential(
            nn.Linear(28*28, 512),
            nn.ReLU(),
            nn.Linear(512, 512),
            nn.ReLU(),
            nn.Linear(512, 10),
        )

    def forward(self, x: Tensor) -> Tensor:
        """피드 포워드(순전파)를 진행하는 함수입니다.

        :param x: 입력 이미지
        :type x: Tensor
        :return: 입력 이미지에 대한 예측값
        :rtype: Tensor
        """
        x = self.flatten(x)
        logits = self.linear_relu_stack(x)
        return logits


def train(dataloader: DataLoader, device: str, model: nn.Module, loss_fn: nn.Module, optimizer: _Optimizer) -> None:
    """MNIST 데이터셋으로 뉴럴 네트워크를 훈련합니다.

    :param dataloader: 파이토치 데이터로더
    :type dataloader: DataLoader
    :param device: 훈련에 사용되는 장치
    :type device: str
    :param model: 훈련에 사용되는 모델
    :type model: nn.Module
    :param loss_fn: 훈련에 사용되는 오차 함수
    :type loss_fn: nn.Module
    :param optimizer: 훈련에 사용되는 옵티마이저
    :type optimizer: torch.optim.Optimizer
    """
    size = len(dataloader.dataset)
    model.train()
    for batch, (X, y) in enumerate(dataloader):
        X, y = X.to(device), y.to(device)

        pred = model(X)
        loss = loss_fn(pred, y)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if batch % 100 == 0:
            loss, current = loss.item(), batch * len(X)
            print(f'loss: {loss:>7f}  [{current:>5d}/{size:>5d}]')


def test(dataloader: DataLoader, device: str, model: nn.Module, loss_fn: nn.Module) -> None:
    """MNIST 데이터셋으로 뉴럴 네트워크의 성능을 테스트합니다.

    :param dataloader: 파이토치 데이터로더
    :type dataloader: DataLoader
    :param device: 훈련에 사용되는 장치
    :type device: str
    :param model: 훈련에 사용되는 모델
    :type model: nn.Module
    :param loss_fn: 훈련에 사용되는 오차 함수
    :type loss_fn: nn.Module
    """
    size = len(dataloader.dataset)
    num_batches = len(dataloader)
    model.eval()
    test_loss = 0
    correct = 0
    with torch.no_grad():
        for X, y in dataloader:
            X, y = X.to(device), y.to(device)
            pred = model(X)
            test_loss += loss_fn(pred, y).item()
            correct += (pred.argmax(1) == y).type(torch.float).sum().item()
    test_loss /= num_batches
    correct /= size
    print(f'Test Error: \n Accuracy: {(100*correct):>0.1f}%, Avg loss: {test_loss:>8f} \n')


def predict(test_data: Dataset, model: nn.Module) -> None:
    """학습한 뉴럴 네트워크로 MNIST 데이터셋을 분류합니다.

    :param test_data: 추론에 사용되는 데이터셋
    :type test_data: Dataset
    :param model: 추론에 사용되는 모델
    :type model: nn.Module
    """
    model.eval()
    x = test_data[0][0]
    y = test_data[0][1]
    with torch.no_grad():
        pred = model(x)
        predicted, actual = pred[0].argmax(0), y
        print(f'Predicted: {predicted}, Actual: {actual}')


def run_pytorch(batch_size: int, epochs: int) -> None:
    """학습/추론 파이토치 파이프라인입니다.

    :param batch_size: 학습 및 추론 데이터셋의 배치 크기
    :type batch_size: int
    :param epochs: 전체 학습 데이터셋을 훈련하는 횟수
    :type epochs: int
    """
    training_data = datasets.MNIST(
        root='data',
        train=True,
        download=True,
        transform=ToTensor(),
    )

    test_data = datasets.MNIST(
        root='data',
        train=False,
        download=True,
        transform=ToTensor(),
    )

    train_dataloader = DataLoader(training_data, batch_size=batch_size, num_workers=16)
    test_dataloader = DataLoader(test_data, batch_size=batch_size, num_workers=8)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    model = NeuralNetwork().to(device)

    loss_fn = nn.CrossEntropyLoss()
    optimizer = optim.SGD(model.parameters(), lr=0.01, momentum=0.9)

    for t in range(epochs):
        print(f'Epoch {t+1}\n-------------------------------')
        train(train_dataloader, device, model, loss_fn, optimizer)
        test(test_dataloader, device, model, loss_fn)
    print('Done!')

    torch.save(model.state_dict(), 'model.pth')
    print('Saved PyTorch Model State to model.pth')

    model = NeuralNetwork()
    model.load_state_dict(torch.load('model.pth'))
    predict(test_data, model)


class NeuralNetworkModule(pl.LightningModule):
    """모델과 학습/추론 코드가 포함된 파이토치 라이트닝 모듈입니다.
    """
    def __init__(self) -> None:
        super(NeuralNetworkModule, self).__init__()
        self.model = NeuralNetwork()
        self.loss_fn = nn.CrossEntropyLoss()
        self.metric = Accuracy(num_classes=10)

    def configure_optimizers(self) -> _Optimizer:
        """옵티마이저를 정의합니다.

        :return: 파이토치 옵티마이저
        :rtype: torch.optim.Optimizer
        """
        return optim.SGD(self.parameters(), lr=0.01, momentum=0.9)

    def forward(self, x: Tensor) -> Tensor:
        """피드 포워딩

        :param x: 입력 이미지
        :type x: Tensor
        :return: 입력 이미지에 대한 예측값
        :rtype: Tensor
        """
        return self.model(x)

    def training_step(self, batch: Tensor, batch_idx: int) -> Dict[str, float]:
        """뉴럴 네트워크를 한 스텝 훈련합니다.

        :param batch: 훈련 데이터셋의 배치 크기
        :type batch: int
        :param batch_idx: 배치에 대한 인덱스
        :type batch_idx: int
        :return: 훈련 오차 데이터
        :rtype: Dict[str, float]
        """
        X, y = batch

        pred = self(X)
        loss = self.loss_fn(pred, y)

        self.log('train_loss', loss, prog_bar=True)

        return {'loss': loss}

    def validation_step(self, batch: Tensor, batch_idx: int) -> Dict[str, float]:
        """훈련 후 한 배치를 검증합니다.

        :param batch: 검증 데이터셋의 배치 크기
        :type batch: int
        :param batch_idx: 배치에 대한 인덱스
        :type batch_idx: int
        :return: 검증 오차 데이터
        :rtype: Dict[str, float]
        """
        X, y = batch

        pred = self(X)
        loss = self.loss_fn(pred, y)
        self.metric.update(pred, y)

        self.log('val_loss', loss, prog_bar=True)

        return {'val_loss': loss}

    def validation_epoch_end(self, outputs: List[Tensor]) -> None:
        """한 에폭 검증을 마치고 실행되는 코드입니다.

        :param outputs: 함수 validation_step에서 반환한 값들을 한 에폭이 끝나는 동안 모은 값들의 집합
        :type outputs: List[Tensor]
        """
        self.log('val_acc', self.metric.compute(), prog_bar=True)
        self.metric.reset()


def run_pytorch_lightning(batch_size: int, epochs: int) -> None:
    """학습/추론 파이토치 라이트닝 파이프라인입니다.

    :param batch_size: 학습 및 추론 데이터셋의 배치 크기
    :type batch_size: int
    :param epochs: 전체 학습 데이터셋을 훈련하는 횟수
    :type epochs: int
    """
    training_data = datasets.MNIST(
        root='data',
        train=True,
        download=True,
        transform=ToTensor(),
    )

    test_data = datasets.MNIST(
        root='data',
        train=False,
        download=True,
        transform=ToTensor(),
    )

    train_dataloader = DataLoader(training_data, batch_size=batch_size, num_workers=16)
    test_dataloader = DataLoader(test_data, batch_size=batch_size, num_workers=8)

    model = NeuralNetworkModule()
    trainer = Trainer(max_epochs=epochs, gpus=1)
    trainer.fit(model, train_dataloaders=train_dataloader, val_dataloaders=test_dataloader)

    trainer.save_checkpoint('model.ckpt')
    print('Saved PyTorch Lightning Model State to model.ckpt')

    model = NeuralNetworkModule.load_from_checkpoint(checkpoint_path='model.ckpt')
    predict(test_data, model)
