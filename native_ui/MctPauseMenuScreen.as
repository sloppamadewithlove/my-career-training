package
{
    import flash.events.Event;

    // Document subclass. Pause, unpause, and input release stay on MidGameMenuScreen.
    // Stock setup can show Friends or expand matchmaking; this screen hides both
    // again for as long as it is attached, including after a later data callback.
    public class MctPauseMenuScreen extends MidGameMenuScreen
    {
        public function MctPauseMenuScreen()
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

        private function keepMatchChrome(event:Event = null) : void
        {
            if (m_shell == null) return;
            if (m_shell.matchmakingView != null && m_shell.matchmakingView.visible) m_shell.hideMatchmakingView();
            if (m_shell.bIsFriendsViewShown) m_shell.hideFriendsView();
        }
    }
}
