import os,sys,traceback
if len(sys.argv) == 4:
    n_part=int(sys.argv[1])
    i_part=int(sys.argv[2])
    exp_dir=sys.argv[3]
else:
    n_part=int(sys.argv[1])
    i_part=int(sys.argv[2])
    i_gpu=sys.argv[3]
    exp_dir=sys.argv[4]
    os.environ["CUDA_VISIBLE_DEVICES"]=str(i_gpu)

import torch
import torch.nn.functional as F
import soundfile as sf
import numpy as np
from fairseq import checkpoint_utils
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

f = open("%s/extract_f0_feature.log"%exp_dir, "a+")
def printt(strr):
    print(strr)
    f.write("%s\n" % strr)
    f.flush()
printt(sys.argv)
# model_path = "/bili-coeus/jupyter/jupyterhub-liujing04/speech/pretrain/ContentVec_legacy500.pt"
model_path = "hubert_base.pt"

printt(exp_dir)
wavPath = "%s/1_16k_wavs"%exp_dir
outPath = "%s/3_feature256"%exp_dir
os.makedirs(outPath,exist_ok=True)
# wave must be 16k, hop_size=320
def readwave(wav_path, normalize=False):
    wav, sr = sf.read(wav_path)
    assert sr == 16000
    feats = torch.from_numpy(wav).float()
    if feats.dim() == 2:  # double channels
        feats = feats.mean(-1)
    assert feats.dim() == 1, feats.dim()
    if normalize:
        with torch.no_grad():
            feats = F.layer_norm(feats, feats.shape)
    feats = feats.view(1, -1)
    return feats
# HuBERT model
printt("load model(s) from {}".format(model_path))
models, saved_cfg, task = checkpoint_utils.load_model_ensemble_and_task(
    [model_path],
    suffix="",
)
model = models[0]
model = model.to(device)
if torch.cuda.is_available():
    model = model.half()
model.eval()

todo=sorted(list(os.listdir(wavPath)))[i_part::n_part]
n = max(1,len(todo) // 10)  # 最多打印十条
if(len(todo)==0):printt("no-feature-todo")
else:
    printt("all-feature-%s"%len(todo))
    for idx,file in enumerate(todo):
        try:
            if file.endswith(".wav"):
                wav_path = "%s/%s"%(wavPath,file)
                out_path = "%s/%s"%(outPath,file.replace("wav","npy"))

                if(os.path.exists(out_path)):continue

                feats = readwave(wav_path, normalize=saved_cfg.task.normalize)
                padding_mask = torch.BoolTensor(feats.shape).fill_(False)
                inputs = {
                    "source": feats.half().to(device) if torch.cuda.is_available() else feats.to(device),
                    "padding_mask": padding_mask.to(device),
                    "output_layer": 9,  # layer 9
                }
                with torch.no_grad():
                    logits = model.extract_features(**inputs)
                    feats = model.final_proj(logits[0])

                feats = feats.squeeze(0).float().cpu().numpy()
                # feats = np.repeat(feats, 2,0) # 20ms -> 10ms
                np.save(out_path, feats, allow_pickle=False)
                if (idx % n == 0):printt("now-%s,all-%s,%s,%s"%(len(todo),idx,file,feats.shape))
        except:
            printt(traceback.format_exc())
    printt("all-feature-done")