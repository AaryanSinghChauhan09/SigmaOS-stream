    # SigmaOS-stream

    IPTV / m3u stream player

    Part of the **SigmaOS** sovereign operating-system ecosystem — a multi-repository
    distribution modelled on Linux Mint and Omarchy Linux. See the parent
    [`SigmaOS`](https://github.com/AaryanSinghChauhan09/SigmaOS) repository for the
    full component index.

    ## Upstream inspirations
    - https://github.com/linuxmint/hypnotix
- https://github.com/sam-blakeman/OmarchyIPTV

    ## Design principles applied
    - **Separation of Concerns**
- **Defensive Programming**
- **Fail-Fast**
- **KISS**
- **Deterministic Testing**

    ## Usage
    Verbs: `parse-m3u, channels, play-plan, favorites`

    ```
    $ sigma-stream parse-m3u channels.m3u
BBC News HD  [News]  https://cdn.example.com/bbcnews/master.m3u8
$ sigma-stream channels channels.m3u --group News
$ sigma-stream play-plan http://edge.example.com/cnn/index.m3u8 --title "CNN"
mpv --really-quiet --force-cache --demuxer-max-bytes=1024KiB ...
$ sigma-stream favorites --add "BBC News HD"

    ```

    ## Build & test
    ```
    make build
    make test
    ```

    ## Licence
    GNU General Public License v3.0 (FOSS).
