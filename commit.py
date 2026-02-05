# DuggerCore Systemic Bridge
try:
    from duggerlink.cli.commit import main
    if __name__ == "__main__":
        main()
except ImportError:
    print("❌ DuggerLinkTools not found!")
    print("🔧 To fix: pip install -e C:\\Github\\DuggerLinkTools")
    print("📋 This installs the global commit engine used by all DuggerCore projects.")
    exit(1)
