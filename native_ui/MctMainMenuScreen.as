package
{
    import flash.display.DisplayObject;
    import flash.display.DisplayObjectContainer;
    import flash.display.InteractiveObject;
    import flash.events.Event;
    import menus.GarageMainMenu;
    import projectx.core.UIMenu;
    import scaleform.clik.core.UIComponent;
    import scaleform.clik.events.ButtonEvent;
    import tagame.core.ITAGameShell;
    import tagame.core.TAGameShellInstance;

    // This class is bound only in the private, owned offline movie. The normal
    // installed movie and its MainMenuScreen class remain unchanged.
    public class MctMainMenuScreen extends MainMenuScreen
    {
        override protected function handleAddedToStage(event:Event) : void
        {
            super.handleAddedToStage(event);
            addEventListener(Event.ENTER_FRAME, keepOfflineChrome, false, 0, true);
            addEventListener(ButtonEvent.CLICK, guardGarageAction, true, int.MAX_VALUE, true);
            keepOfflineChrome();
        }

        override protected function handleRemovedFromStage(event:Event) : void
        {
            removeEventListener(Event.ENTER_FRAME, keepOfflineChrome);
            removeEventListener(ButtonEvent.CLICK, guardGarageAction, true);
            super.handleRemovedFromStage(event);
        }

        override protected function addEventListeners() : void
        {
            // The base registers challenges/R1, friends, debug purchases and
            // matchmaking-search callbacks here. Camera controls own their
            // listeners separately and the base stack/resize handling remains.
        }

        override protected function onMatchmakingSearching() : void
        {
            // This screen has no Find Match route in the offline career.
        }

        override protected function handleMenuStackChange(event:Event = null) : void
        {
            super.handleMenuStackChange(event);
            keepOfflineChrome();
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

        private function blockedGarageControls(garage:GarageMainMenu) : Array
        {
            return [garage.premiumInventoryButton, garage.tradeInButton,
                garage.blueprintsButton, garage.rewardsButton];
        }

        private function guardGarageAction(event:ButtonEvent) : void
        {
            var garage:GarageMainMenu = UIMenu.getActiveMenu() as GarageMainMenu;
            if (garage == null) return;
            // Capture before the stock button handler, including a controller
            // click if a game-data callback made a control visible this frame.
            for each (var blocked:DisplayObject in blockedGarageControls(garage))
            {
                var target:DisplayObject = event.target as DisplayObject;
                while (target != null && target != garage)
                {
                    if (target == blocked)
                    {
                        event.preventDefault();
                        event.stopImmediatePropagation();
                        return;
                    }
                    target = target.parent;
                }
            }
        }

        private function keepGarageLocal() : void
        {
            var garage:GarageMainMenu = UIMenu.getActiveMenu() as GarageMainMenu;
            if (garage == null) return;
            for each (var blocked:DisplayObject in blockedGarageControls(garage)) disable(blocked);
            // Keep car customization and preset controls, without their shared
            // BranchingMenu shortcut into an expanded matchmaking panel.
            for each (var control:UIComponent in [garage.presetSwitcher, garage.customizeCarButton,
                garage.createPresetButton, garage.renamePresetButton, garage.deletePresetButton])
                if (control != null) control.focusFunction = null;
        }

        private function keepOfflineChrome(event:Event = null) : void
        {
            keepGarageLocal();
            disable(challengesSummaryView);
            disable(topSpinachDebugButton1);
            disable(topSpinachDebugButton2);
            disable(topSpinachDebugButton3);
            disable(worldCupDebugButton1);
            var shell:ITAGameShell = TAGameShellInstance.get();
            if (shell == null) return;
            // These are UI state changes in this offline process. Returning to
            // normal online play closes it and starts the unmodified game.
            shell.bShowNewsView = false;
            if (event == null) shell.hideTopNavigation();
            if (shell.matchmakingView != null && shell.matchmakingView.visible) shell.hideMatchmakingView();
            if (shell.bIsFriendsViewShown) shell.hideFriendsView();
            if (shell.isShownSupportCreatorView) shell.hideSupportCreatorView();
            disable(shell.tournamentNotification);
            if (shell.taskBar != null)
            {
                if (event == null || shell.getIsTaskBarVisible())
                {
                    shell.taskBar.setInactive();
                    shell.hideTaskBar();
                }
                disable(shell.taskBar);
            }
        }
    }
}
