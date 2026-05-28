#!/bin/bash

# Setup script to install git hooks for Hackathon repository
# Run this after cloning the repository to enable branch protection

echo "🔧 Setting up git hooks for Hackathon repository..."

# Create pre-push hook
cat > .git/hooks/pre-push << 'EOF'
#!/bin/bash

# Pre-push hook to prevent direct pushes to main branch
# This ensures teams can only push to their own team branches

protected_branch='main'

while read local_ref local_sha remote_ref remote_sha
do
    if [ "$remote_ref" = "refs/heads/$protected_branch" ]; then
        echo ""
        echo "❌ ERROR: Direct push to '$protected_branch' branch is not allowed!"
        echo ""
        echo "To work on this repository:"
        echo "  1. Create a team branch: git checkout -b team-<your-team-name>"
        echo "  2. Make your changes and commit them"
        echo "  3. Push to your team branch: git push origin team-<your-team-name>"
        echo ""
        echo "Example:"
        echo "  git checkout -b team-alpha"
        echo "  git add ."
        echo "  git commit -m 'Your changes'"
        echo "  git push origin team-alpha"
        echo ""
        exit 1
    fi
done

exit 0
EOF

# Make hook executable
chmod +x .git/hooks/pre-push

echo "✅ Git hooks installed successfully!"
echo ""
echo "Note: Direct pushes to 'main' branch are now blocked locally."
echo "Teams should work on branches named: team-<teamname>"
