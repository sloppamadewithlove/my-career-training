# Community plugin library

The development source can check a BakkesPlugins release by its numeric page ID
and download the package into My Career's private library. For example,
[Workshop Map Loader & Downloader](https://bakkesplugins.com/plugin/223) is ID
`223`. Other IDs can be checked through the same official metadata service.
The short metadata endpoint supplies no title or creator name. Uncurated IDs
therefore display as **Community plugin [ID]**, with a canonical creator-page address in the metadata;
the app does not invent a name or infer compatibility from the filename.

In the existing plugin interface, open **Workshop → Community plugin downloads**.
The desktop development interface also exposes this under **Community**. Check
the current release, then explicitly choose **Download to library**. These
controls are not a replacement for Rocket League's native menu and are not in
the old public installer.

Downloaded packages remain **downloaded, not enabled**. The service checks
transport, size, archive structure and member CRCs, records SHA-256, and leaves the original
archive in the per-user cache. It never extracts the archive into BakkesMod,
changes autoload configuration, executes an installer, or loads a DLL. A hash
identifies downloaded bytes; it does not certify their publisher or behavior.
The site's `verified` field is a BakkesPlugins listing status.

Enabling arbitrary community plugins is not implemented. The current host uses
a shared BakkesMod directory, and a third-party plugin can persist its own state.
The existing My Career recovery journal does not prove that third-party code
would stay out of an ordinary Steam launch after a crash. Before activation is
added, verify an isolated or process-scoped loading route, each plugin's exact
artifact/dependencies, cleanup after crashes, and a subsequent normal Steam
launch. Do not add third-party autoload lines as a shortcut around this boundary.

The official [PluginManager source](https://github.com/bakkesmodorg/PluginManager/blob/master/PluginManager/PluginManager.cpp)
documents the ID-based metadata service. This project uses normal certificate
validation and checks redirect destinations. It does not copy the upstream
package extraction or TLS-disabled download behavior.
