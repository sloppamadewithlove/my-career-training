# Native My Career movie

`menus/MctRootMenu.as` is original code. `compiled/MctRootMenu.abc` is its
compiled AVM2 code, intended for a private, version-checked menu composition.
It is not a replacement game file and is not enabled in the release.

Development build shape, using an already prepared private external SDK:

```text
mxmlc -target-player=32.0 -swf-version=20 -source-path=native_ui 
  -external-library-path+=PRIVATE/MainMenu-private-sdk-abc.swc 
  -output=PRIVATE/MctRootMenu-only.swf native_ui/menus/MctRootMenu.as
```

Inspect the output before extracting its single DoABC payload. Require exactly
the original mod class and no linked game classes. The `VIEW_URL` and `SESSION`
placeholder strings are bound for the owned session when composing the private
movie. See [the protocol and validation limits](../docs/NATIVE_MOVIE_PROTOCOL.md).

Keep private SDKs and game assets out of this directory. These build tools are
developer dependencies, not player prerequisites.
