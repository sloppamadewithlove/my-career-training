package
{
    import flash.display.DisplayObject;
    import flash.display.DisplayObjectContainer;
    import flash.display.InteractiveObject;
    import flash.events.Event;
    import scaleform.clik.core.UIComponent;
    import tagame.core.ITAGameShell;
    import tagame.core.TAGameShellInstance;

    // Document subclass. Scoreboard ownership and screen lifecycle stay on EndGameMenuScreen.
    public class MctResultsMenuScreen extends EndGameMenuScreen
    {
        public function MctResultsMenuScreen()
        {
            super();
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
            super.handleRemovedFromStage(event);
        }

        override protected function transitionToState(state:String) : void
        {
            super.transitionToState(state);
            // The stock Menu transition activates the taskbar synchronously.
            // Retire its controls before another input event can reach them.
            keepMatchChrome();
        }

        private function keepMatchChrome(event:Event = null) : void
        {
            var shell:ITAGameShell = TAGameShellInstance.get();
            if (shell == null) return;
            if (shell.matchmakingView != null && shell.matchmakingView.visible) shell.hideMatchmakingView();
            if (shell.bIsFriendsViewShown) shell.hideFriendsView();
            if (shell.taskBar != null)
            {
                if (event == null || shell.getIsTaskBarVisible())
                {
                    // The stock results transition can show this again after
                    // attach. Retire its party/friends input each time it does.
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
