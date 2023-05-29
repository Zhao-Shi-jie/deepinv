import git
import requests
import shutil
import os
import zipfile
import torch
import torchvision
import numpy as np


class MRIData(torch.utils.data.Dataset):
    """fastMRI dataset (knee subset)."""

    def __init__(
        self, root_dir, train=True, sample_index=None, tag=900, transform=None
    ):
        x = torch.load(str(root_dir) + ".pt")
        x = x.squeeze()
        self.transform = transform

        if train:
            self.x = x[:tag]
        else:
            self.x = x[tag:, ...]

        self.x = torch.stack([self.x, torch.zeros_like(self.x)], dim=1)

        if sample_index is not None:
            self.x = self.x[sample_index].unsqueeze(0)

    def __getitem__(self, index):
        x = self.x[index]

        if self.transform is not None:
            x = self.transform(x)

        return x

    def __len__(self):
        return len(self.x)


def get_git_root():
    git_repo = git.Repo(".", search_parent_directories=True)
    git_root = git_repo.git.rev_parse("--show-toplevel")
    return git_root


def load_dataset(
    dataset_name, data_dir, transform, download=True, url=None, train=True
):
    dataset_dir = data_dir / dataset_name

    if dataset_name == "fastmri_knee_singlecoil":
        filetype = "pt"
    else:
        filetype = "zip"

    if download and not dataset_dir.exists():
        dataset_dir.mkdir(parents=True, exist_ok=True)
        if url is None:
            url = (
                f"https://mycore.core-cloud.net/index.php/s/9EzDqcJxQUJKYul/"
                f"download?path=%2Fdatasets&files={dataset_name}.{filetype}"
            )
            with open(str(dataset_dir) + f".{filetype}", "wb") as f:
                request = requests.get(url)
                f.write(request.content)

            if filetype == "zip":
                with zipfile.ZipFile(str(dataset_dir) + ".zip") as zip_ref:
                    zip_ref.extractall(str(data_dir))

                # remove temp file
                os.remove(str(dataset_dir) + f".{filetype}")
                print(f"{dataset_name} dataset downloaded in {data_dir}")
            else:
                shutil.move(
                    str(dataset_dir) + f".{filetype}",
                    str(dataset_dir / dataset_name) + f".{filetype}",
                )

    if dataset_name == "fastmri_knee_singlecoil":
        dataset = MRIData(
            train=train, root_dir=dataset_dir / dataset_name, transform=transform
        )
    else:
        dataset = torchvision.datasets.ImageFolder(
            root=dataset_dir, transform=transform
        )
    return dataset


def load_degradation(name, data_dir, kernel_index=0, download=True):
    kernel_path = data_dir / name
    if download and not kernel_path.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        url = f"https://mycore.core-cloud.net/index.php/s/9EzDqcJxQUJKYul/download?path=%2Fdatasets&files={name}"

        with requests.get(url, stream=True) as r:
            with open(str(data_dir / name), "wb") as f:
                shutil.copyfileobj(r.raw, f)
        print(f"{name} degradation downloaded in {data_dir}")

    kernels = np.load(kernel_path, allow_pickle=True)
    kernel_torch = torch.from_numpy(kernels[kernel_index])  # .unsqueeze(0).unsqueeze(0)
    return kernel_torch