import os
from os.path import exists, abspath
import sys
import logging
import argparse
import subprocess
import warnings

import torch
from torchbench_utils import *
from benchmark_remat_utils import profile_model, check_remat_info_model


"""
Benchmark rematerialization algorithm on full graphs of torchbench models

Example:

python benchmarks/benchmark_remat_fullgraphs.py --isolate --devices='cuda' -k 'timm_nfnet'

You can also use the -k flag to append other models to run. If no -k models are specified, it will run all models (some will fail due to more than 1 graph in the model).

If you only want to see how much memory will be reduced by the mincut optimization, WITHOUT actually benchmarking the performance, you can use the --info flag.
"""


current_dir = os.getcwd()
torch.backends.cuda.matmul.allow_tf32 = True


os.environ["KALDI_ROOT"] = "/tmp"  # avoids some spam
for torchbench_dir in (
    "../torchbenchmark",
    "../torchbench",
    "../benchmark",
):
    if exists(torchbench_dir):
        break
assert exists(torchbench_dir), "../torchbenchmark does not exist"
torchbench_dir = abspath(torchbench_dir)
os.chdir(torchbench_dir)
sys.path.append(torchbench_dir)
log = logging.getLogger(__name__)


models_to_run = [
#    'timm_nfnet',
#     # 'BERT_pytorch',
#     'resnet50',
#     'timm_regnet',
#     'resnext50_32x4d',
#     'mobilenet_v2_quantized_qat',
#     'LearningToPaint',
#     'resnet18',
#     'timm_efficientnet',
#     'pytorch_struct',

]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--filter", "-k", action="append", help="filter benchmarks with regexp"
    )
    parser.add_argument(
        "--exclude", "-x", action="append", help="filter benchmarks with regexp"
    )
    parser.add_argument("--devices", "-d", action="append", help="cpu or cuda")
    parser.add_argument("--only", help="used by --isolate to run just one model")
    parser.add_argument(
        "--isolate", action="store_true", help="run each model in its own process"
    )

    parser.add_argument(
        "--info", action="store_true", help="only print out info without benchmarking"
    )

    args = parser.parse_args()
    args.devices = args.devices or ["cpu"]
    args.filter = args.filter or [r"."]
    args.exclude = args.exclude or [r"^$"]
    args.training = True

    # nvfuser:
    torch._C._jit_override_can_fuse_on_cpu(False)
    torch._C._jit_override_can_fuse_on_gpu(False)
    torch._C._jit_set_texpr_fuser_enabled(False)
    torch._C._jit_set_nvfuser_enabled(True)

    if args.only:
        for device in args.devices:
            torch.manual_seed(1337)
            try:
                device, name, model, example_inputs = load_model(
                    device, args.only, args.training, True  # use_eval_mode=True
                )
            except NotImplementedError:
                continue  # bad benchmark implementation

            if args.info:
                check_remat_info_model(name, model, example_inputs)
            else:
                profile_model(name, model, example_inputs)

    elif args.isolate:
        if args.info:
            print("name, num_fusion_group, num_remat_group, memory_reduced, num_node_pairs", flush=True)
        else:
            print("name, eager_time, scripted_cuda_time, fused_cuda_time, remat_cuda_time, num_fusion_group, num_remat_group, memory_reduced", flush=True)
        os.chdir(current_dir)
        for name in iter_model_names(args):
            if len(models_to_run) > 0 and name not in models_to_run:
                continue
            try:
                subprocess.check_call([sys.executable] + sys.argv + [f"--only={name}"])
            except subprocess.SubprocessError:
                print(name,"ERROR")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    warnings.filterwarnings("ignore")
    main()