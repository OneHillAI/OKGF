# Homebrew formula for the OKGF validator.
#
# This is the source of truth to copy into the tap repository (OneHillAI/homebrew-tap) as
# Formula/okgf.rb. Users then install with:
#
#   brew install OneHillAI/tap/okgf
#
# The `url`/`sha256` below point at the PyPI sdist for a given version. On each release they are
# updated to the new version and its checksum (the release workflow can run `brew bump-formula-pr`,
# or a maintainer updates them by hand). The PyYAML resource is the only runtime dependency.
class Okgf < Formula
  include Language::Python::Virtualenv

  desc "Reference validator for the Open Knowledge and Governance Format (OKGF)"
  homepage "https://onehill.org/okgf"
  url "https://files.pythonhosted.org/packages/source/o/okgf/okgf-0.1.0.tar.gz"
  sha256 "REPLACE_WITH_OKGF_SDIST_SHA256"
  license "Apache-2.0"

  depends_on "python@3.12"

  resource "PyYAML" do
    url "https://files.pythonhosted.org/packages/source/P/PyYAML/pyyaml-6.0.2.tar.gz"
    sha256 "REPLACE_WITH_PYYAML_SDIST_SHA256"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "okgf #{version}", shell_output("#{bin}/okgf --version")

    (testpath/"index.md").write <<~EOS
      ---
      okf_version: "0.1"
      type: Index
      title: Test bundle
      ---
      # Test bundle
    EOS
    assert_match "0 error(s)", shell_output("#{bin}/okgf #{testpath}")
  end
end
