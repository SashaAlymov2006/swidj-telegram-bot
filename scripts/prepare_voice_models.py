"""Warm official local Whisper models in the persistent model-cache volume.

Default: Mini App base. --all also prepares the chat model from WHISPER_MODEL.
Run in the bot container as its normal user, without restarting the bot.
"""
import argparse,gc,os

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--all',action='store_true');args=parser.parse_args()
    import torch,whisper
    torch.set_num_threads(2)
    models=['base']
    if args.all:models=list(dict.fromkeys(models+[os.getenv('WHISPER_MODEL','medium')]))
    for name in models:
        model=whisper.load_model(name,device='cpu');del model;gc.collect()
        print('Local voice model ready: '+name,flush=True)

if __name__=='__main__':main()
