{pkgs}: {
  deps = [
    pkgs.libxcrypt
    pkgs.geos
    pkgs.postgresql
    pkgs.openssl
  ];
}
