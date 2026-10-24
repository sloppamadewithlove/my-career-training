package
{
    import menus.MctRootMenu;

    // Compiled under this unique name because the private SDK already exports
    // RootMenuMovie and that external name wins a compile-time collision.
    // The movie composer renames this one constant-pool string to RootMenuMovie
    // after it binds the session. This constructor does not load a view.
    public dynamic class MctRootMenuMovie extends MctRootMenu
    {
        public function MctRootMenuMovie()
        {
            super();
        }
    }
}
