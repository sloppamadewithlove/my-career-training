#include "NativeWorkshopDispatch.h"
#include <iostream>
#include <string>
#include <vector>

int main() {
#ifdef _WIN32
    const std::string path = "C:\\Steam Library\\steamapps\\workshop\\content\\252950\\1234\\Map.upk";
#else
    const std::string path = "/Steam Library/steamapps/workshop/content/252950/1234/Map.upk";
#endif
    const std::string command = "load_workshop \"" + path + "\"";
    std::vector<std::string> sent;
    const auto send = [&](const std::string& text) { sent.push_back(text); };
    if (!mct::dispatchNativeWorkshopCommand(command, true, send) || sent != std::vector<std::string>{command}) {
        std::cerr << "A valid generated workshop command did not reach the host callback\n";
        return 1;
    }
    for (const auto& invalid : {"load_workshop \"\"", "load_workshop \"relative.upk\"",
                               "load_workshop \"C:\\Map.upk\";exit", "exit", "load_workshop C:\\Map.upk"}) {
        if (mct::dispatchNativeWorkshopCommand(invalid, true, send)) return 2;
    }
    if (mct::dispatchNativeWorkshopCommand(command, false, send) || sent.size() != 1) return 3;
    std::cout << "native workshop host dispatch passed\n";
    return 0;
}
