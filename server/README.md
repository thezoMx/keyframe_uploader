# keyframe-uploader

Batch-upload Roblox `KeyframeSequence`s to Open Cloud and get `Animation` instances back.

A Studio plugin sends your selected KeyframeSequences to a local server (`rpx`). The
server rebuilds each as a binary `.rbxm`, uploads it through the Open Cloud Assets API,
and returns the asset ids so the plugin can build `Animation` instances.

## Install

```
pip install keyframe-uploader
rpx setup
rpx
```

`rpx setup` asks for your Open Cloud API key and creator id, installs rojo, and links you
to the Studio plugin. `rpx where` shows status. `rpx` starts the server.

## Requirements

- Python 3.8+ (Windows)
- A Roblox Open Cloud API key with Assets read + write
- rojo (installed for you by `rpx setup`)

## License

MIT
