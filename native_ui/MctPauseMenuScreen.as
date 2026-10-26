package
{
    import flash.display.DisplayObject;
    import flash.display.DisplayObjectContainer;
    import flash.display.InteractiveObject;
    import flash.events.Event;
    import menus.MctPauseMenu;
    import tagame.api.DevUtil;
    import scaleform.clik.core.UIComponent;
    import tagame.core.ITAGameShell;
    import tagame.core.TAGameShellInstance;

    // Document subclass. Pause, unpause, and input release stay on MidGameMenuScreen.
    // Stock setup reactivates the party taskbar and online shortcuts. Keep the
    // same offline shell boundary as the authored frontend while attached.
    public class MctPauseMenuScreen extends MidGameMenuScreen
    {
        private var lastReturnHeld:Boolean = false;

        public function MctPauseMenuScreen()
        {
            super();
        }

        override public function close(fadeTime:Number = -1) : void
        {
            var authored:MctPauseMenu = midGameMenu as MctPauseMenu;
            if (authored != null && authored.shouldHoldScreenClose())
            {
                DevUtil.Log("MCT_NATIVE_RETURN_DIAG", "pause:document_close_blocked");
                return;
            }
            DevUtil.Log("MCT_NATIVE_RETURN_DIAG", "pause:document_close_allowed");
            super.close(fadeTime);
        }

        override protected function handleAddedToStage(event:Event) : void
        {
            super.handleAddedToStage(event);
            addEventListener(Event.ENTER_FRAME, keepMatchChrome, false, 0, true);
            keepMatchChrome();
        }

        override protected function handleRemovedFromStage(event:Event) : void
        {
            removeEventListener(Event.ENTER_FRAME, keepMatchChrome);
            // Observation only: manager/native removal can bypass close().
            // Never suppress stock removal cleanup or claim this is arrival.
            DevUtil.Log("MCT_NATIVE_RETURN_DIAG", lastReturnHeld ?
                "pause:document_removed_after_held_frame" : "pause:document_removed");
            lastReturnHeld = false;
            super.handleRemovedFromStage(event);
        }

        private function keepMatchChrome(event:Event = null) : void
        {
            var authored:MctPauseMenu = midGameMenu as MctPauseMenu;
            lastReturnHeld = authored != null && authored.shouldHoldScreenClose();
            var shell:ITAGameShell = TAGameShellInstance.get();
            if (shell == null) return;
            if (shell.matchmakingView != null && shell.matchmakingView.visible) shell.hideMatchmakingView();
            if (shell.bIsFriendsViewShown) shell.hideFriendsView();
            if (shell.taskBar != null)
            {
                if (event == null || shell.getIsTaskBarVisible())
                {
                    // Hiding alone leaves PartyView and global input listeners
                    // active. Use the stock teardown before disabling its tree.
                    shell.taskBar.setInactive();
                    shell.hideTaskBar();
                }
                disable(shell.taskBar);
            }
        }

        private function disable(control:DisplayObject) : void
        {
            if (control == null) return;
            control.visible = false;
            if (control is InteractiveObject)
            {
                InteractiveObject(control).mouseEnabled = false;
                InteractiveObject(control).tabEnabled = false;
            }
            if (control is DisplayObjectContainer)
            {
                DisplayObjectContainer(control).mouseChildren = false;
                DisplayObjectContainer(control).tabChildren = false;
            }
            if (control is UIComponent)
            {
                UIComponent(control).enabled = false;
                UIComponent(control).focusable = false;
                UIComponent(control).focusFunction = null;
            }
        }
    }
}
