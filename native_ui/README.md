# Native My Career movie

`menus/MctRootMenu.as`, `MctMainMenuScreen.as`, and `MctRootMenuMovie.as` are original code.
`compiled/MctRootMenu.abc` contains their compiled AVM2 code, intended for a
private, version-checked menu composition.
It is not a replacement game file and is not enabled in the release.

`MctRootMenuMovie` is a public dynamic, zero-argument wrapper around `menus.MctRootMenu`.
It is compiled under that name because the private SDK already exports
`RootMenuMovie`. The composer renames the compiled string to `RootMenuMovie`
after session binding and renames the original movie's `RootMenuMovie` string
to `MctOriginalRootMenuMovie`. It does not reparent the original class.

Development build shape, using an already prepared private external SDK:

```text
mxmlc -debug=false -target-player=32.0 -swf-version=20 -source-path=native_ui
  -includes=MctMainMenuScreen,MctRootMenuMovie
  -external-library-path+=PRIVATE/MainMenu-private-sdk-abc.swc
  -output=PRIVATE/MctRootMenu-only.swf native_ui/menus/MctRootMenu.as
```

Inspect the output before extracting its single DoABC payload. Require exactly
the three original mod classes and no linked game classes. The `VIEW_URL` and `SESSION`
placeholder strings are bound for the owned session when composing the private
movie. See [the composition limits](../docs/NATIVE_MOVIE_COMPOSE.md).

Keep private SDKs and game assets out of this directory. These build tools are
developer dependencies, not player prerequisites.
