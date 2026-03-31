from pathlib import Path

import pooch

ancillary_data = {
    "dd4702303a67c35fb6c6153974c242544d8e4366fd96a04e125b6f716cf063cd": "./land_data/prvi.json",
    "ea81138e8a350743702f5460e1b23f12aeb9133c15630b9cc1b61bafe9c8e71b": "./land_data/glna.json",
    "4f7a6951e07d92f67b669cbe02ed29c7fe8f665162d5736cf0b2b8663f334f40": "./land_data/uswc.json",
    "e3f1f99613485e46cfb54264d0553df51b3164512c50b8383ce91a15918aa9b6": "./land_data/gak.json",
    "ed24bc1281fcf547d13347fc4310e206361cf1937e319ca90cf5a3fa144a9c54": "./land_data/usegc.json",
    "35e73623c5d18db06ff93020cf1e55040ef8b2574a6e16dcf6101de80100c4ac": "./land_data/ushi.json",
    "72ae72409a488d23c87883fda65e3c353f79c7969bd5b6d9f4e8ce8bbc87c348": "./land_data/akns.json",
    "9160060194d4409fac92cb5d326083b195324b0b993cf16e9cba7b228e1600f8": "./grid_data/gak6km.nc",
    "6d04512bb221e8f3ff59fd163d3fb5f2fa8cb2e04445f09ac6bf6313720d0133": "./grid_data/akns6km.nc",
    "ab1c3c0f8d236d1cfa168c00e9f437d7c8eeba40d3719772832f432da9654612": "./grid_data/gak2km.nc",
    "f9a5e83b6f93beb6473fe5209096baad3084cc9d02b6c25b297d5da648b0fc7f": "./grid_data/uswc2km.nc",
    "5de3c4e27830e17dbf836f1d0a144f3530c3dc249f6667895967136cf3200020": "./grid_data/usegc2km.nc",
    "9ed6c7f9d8028237e1d0886846e48e1c7fa0b342426437f3a1fdf4848ef7f0c8": "./grid_data/uswc1km.nc",
    "f3d293ca434938dd6608da3b6cda5a3d0b5f1ed92db0ab0ffaef79a8b1723e48": "./grid_data/ushi1km.nc",
    "cad1f795af537576b640f86376192f6370021b8608cc30498a69c18486cff25c": "./grid_data/glna6km.nc",
    "e7223e4dfa36f816ab426a7c6c205c5007aeb2db3d757f94774a6314cd805189": "./grid_data/ushi2km.nc",
    "38e123f9cb03c270014777a8bd607f9d1423344da001b13d31ed3ef8234c3418": "./grid_data/akns2km.nc",
    "7db27f02e2532179ae7590aedc7995201c209169902e96b91b90eca51e47ef6e": "./grid_data/usegc6km.nc",
    "8233ead574ef3b5389e85a95adcb45369c69e2fd6598ff67476202ed1235cc15": "./grid_data/usegc1km.nc",
    "4618893662fc02eff059d4b46e71730910c495bb4bb9fcda64023e06ff6bd87c": "./grid_data/prvi2km.nc",
    "ae1311212d3aa4ef32e7ead3b2c0c7f4b45bbbe7356ba13564a3261738bcd250": "./grid_data/ushi6km.nc",
    "e33e373e0408a20247d8002d256bcce1c09718241648addc7d5c71393b79a062": "./grid_data/akns1km.nc",
    "e773cb3b869dbd62a578f81fa23689824861b6e1c463320ee18703d12ed5a0f6": "./grid_data/prvi6km.nc",
    "a2463d7c11d86b4dbcf33d8d3c2c78c95a31eed69412914704dba2484212676c": "./grid_data/glna500m.nc",
    "4bf7bae857636c8ad09ded82637c68dba6d5d911a7b154828886f8d1797f497f": "./grid_data/uswc500m.nc",
    "5fea508713302f90fb3cd2dc5f894d5b07f86ad5a0ef11a16b106460ac84b8d9": "./grid_data/prvi1km.nc",
    "8e05b44fa70404ccee58ad7312936bb85d5bff13961c6ec7bfad9a39c39f931f": "./grid_data/glna2km.nc",
    "5285e88d30f38c2a99b3ce79d20811fee0260da5ba6d8dc8e62dfb53765b045c": "./grid_data/uswc6km.nc",
    "2a2f56dcfb154561ecaa2eafc2ed1cb970deb23b697d47d70bed276c9183f516": "./grid_data/glna1km.nc",
    "a98f84346b0330d79ba41709212b9febbaddf99c955145e702339e32e4f79b3e": "./grid_data/gak1km.nc",
}

def download_ancillary_data(fname, sha256):
    url = "https://github.com/ioos/hfrnet-rtv/releases/download"
    version = "2026.04.01"

    p = Path(fname)
    fname = pooch.retrieve(
        path=f"ancillary_data/{p.parent}",
        fname=p.name,
        url=f"{url}/{version}/{p.name}",
        known_hash=f"sha256:{sha256}",
    )

if __name__ == "__main__":
    for sha256, fname in ancillary_data.items():
        download_ancillary_data(fname, sha256)
