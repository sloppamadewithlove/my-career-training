#include "MyCareerTraining.h"
#include <stdexcept>

// Supported SDK dialogs only. No event parameter casts, Unreal object offsets,
// binary patches, package replacement, or undocumented calls are used here.
void MyCareerTraining::closeNativeMenu() {
    ++nativeGeneration_; // Make queued callbacks inert before closing the dialog.
    nativeDialogActive_ = false;
    if (nativeModal_) {
        // The game owns native objects. Once the world has changed, don't call
        // through a wrapper retained from the old frontend.
        if (!gameWrapper->IsInGame() && !gameWrapper->IsInReplay()) nativeModal_->CloseModal();
        nativeModal_.reset();
    }
    nativeNonce_.clear();
}

void MyCareerTraining::showNativeMenu() {
    closeNativeMenu();
    if (!ownedOfflineNow() || gameWrapper->IsInGame() || gameWrapper->IsInReplay())
        throw std::runtime_error("Return to the owned offline frontend before trying native dialogs.");
    const auto state = bridge_->state();
    const auto view = nativeMenu_.view(state);
    nativeNonce_ = mct::stringValue(state, "bridge_session");
    auto modal = gameWrapper->CreateModal(view.title);
    if (modal.memory_address == 0) throw std::runtime_error("This game build did not create a native dialog.");
    nativeModal_ = std::make_unique<ModalWrapper>(modal);
    nativeModal_->SetBody(view.body);
    const auto generation = nativeGeneration_;
    const auto nonce = nativeNonce_;
    std::weak_ptr<int> life = alive_;
    for (const auto& choice : view.choices) {
        nativeModal_->AddButton(choice.label, choice.cancel, [this, life, choice, generation, nonce] {
            if (life.expired()) return;
            // A native click may run while its dialog is dispatching callbacks.
            // Defer closing/creating the next dialog to our next game-thread tick.
            std::lock_guard<std::mutex> guard(runtimeMutex_);
            if (!nativeClick_) nativeClick_ = NativeClick{choice, nonce, generation};
        });
    }
    menuOpen_ = false;
    nativeDialogActive_ = true;
    nativeModal_->ShowModal();
    nativeMenuMessage_ = "Native dialog trial opened. Back/Escape and controller behavior still require in-game testing.";
}

void MyCareerTraining::processNativeClick() {
    std::optional<NativeClick> click;
    {
        std::lock_guard<std::mutex> guard(runtimeMutex_);
        click.swap(nativeClick_);
    }
    if (!click) return;
    if (click->generation != nativeGeneration_ || !nativeDialogActive_ || !ownedOfflineNow() ||
        gameWrapper->IsInGame() || gameWrapper->IsInReplay() ||
        click->nonce != mct::stringValue(bridge_->state(), "bridge_session")) return;
    const auto result = nativeMenu_.choose(click->choice, bridge_->state());
    if (!result.accepted) {
        nativeMenuMessage_ = "That choice changed while the dialog was open. Review the current career state.";
        closeNativeMenu();
        menuOpen_ = true;
        cvarManager->executeCommand("openmenu mycareertraining", false);
        return;
    }
    closeNativeMenu();
    if (!result.action.empty()) {
        // Ownership and offline status are checked on this game thread again.
        // The backend separately checks expected fixture IDs before modifying a save.
        if (!ownedOfflineNow() || !bridge_->send(result.action, result.payload))
            throw std::runtime_error("The offline service did not accept this native menu request.");
        nativeMenuMessage_ = "Native dialog sent " + result.action + ". The service reports the actual outcome.";
    }
    if (!result.close) showNativeMenu();
    else if (result.action.empty()) {
        menuOpen_ = true;
        cvarManager->executeCommand("openmenu mycareertraining", false);
    }
}
