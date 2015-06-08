#pcp-sdn

This project implements Port Control Protocol (PCP) server as a network application running on an SDN controller.

Additionally, the project integrates a custom implementation of a simple NAT gateway, split into control plane (also running on the controller) and data plane (represented as flow entries on forwarder(s) performing address and port translation).

The PCP server implementation aims to be compliant with RFC 6887. However, the current state of the implementation does not support the following parts of the RFC:
* wildcard matching of internal ports and protocols,
* generating PCP responses with non-SUCCESS result code back to PCP client,
* parsing and processing options,
* processing of PCP ANNOUNCE requests,
* state recovery mechanisms (e.g. restoring lost mappings when the PCP client or PCP server crashes and reboots)
* if a PCP mapping is created, an implicit mapping that forwards ICMP messages is not created,
* the implementation only supports TCP and UDP as upper-layer protocols.

The current implementation also does not define any PCP server address, i.e. PCP clients can use any IP address as the PCP server address when sending PCP requests.


#Installation

Requirements:
* Ubuntu 14.04 or newer
* [ryu SDN framework](https://github.com/osrg/ryu)
* [ofsoftswitch13](https://github.com/unifycore/ofsoftswitch13)
* [PCP client library](https://github.com/libpcp)
* optional: `nping` command as a part of the `nmap` package (to test address and port translation for TCP connections)

To install ryu and ofsoftswitch13, you may utilize the [UnifyCore](https://github.com/unifycore/unifycore) project and run its install script `unifycore/support/install_core.sh`. Note, however, that in that case you'll need to install Ubuntu Server 14.04 (as per the requirements of UnifyCore).

Alternatively, you may install ryu and ofsoftswitch13 without UnifyCore. In that case, follow the installation instructions for ryu and ofsoftswitch13.

##Compiling the PCP client

To compile the PCP client, run the following commands:
    
    cd [path to PCP client library directory]
    ./autogen.sh
    ./configure
    make
    sudo make install


#Usage

The source contains a script for the following test topology:
    
                         Controller
                             |
                             |
         Host 1 --------- Forwarder --------- Host 2
    172.16.0.100/24                       200.0.0.200/24

The controller runs the PCP server and the control plane for NAT. The forwarder forwards PCP messages between hosts and the controller, translates IP addresses and ports and forwards messages between Host 1 and Host 2.

Run the `read_command_output.sh` script for all commands that will be generating log output:
    
    read_command_output.sh 'ryu-manager'
    read_command_output.sh 'ofdatapath'
    read_command_output.sh 'ofprotocol'

Run the test topology script:
    
    pcp_sdn_test_topology.sh

The script generates the topology, initializes the controller with the network application (PCP server + NAT) and initializes the forwarder.

To request mapping information from Host 1 for a specific port (the `[port]` parameter), run the PCP client from the Host 1 namespace:
    
    sudo ip netns exec 'host1' pcp -i [Host 1 IP address]:[port] -l [mapping lifetime] -s [PCP server address]

The PCP server will create a TCP mapping. To create a UDP mapping, specify the `-u` option. Since the current implementation does not check for the PCP server IP address, you may specify any address.

To test TCP communication between Host 1 (in a private network) and Host 2 (in a public network), you may use `nping` to generate TCP segments. Run the `nping` server on Host 2:
    
    sudo ip netns exec 'host2' nping --echo-server 'test' -v4

Send TCP segments from Host 1 by running the `nping` client:
    
    sudo ip netns exec 'host1' nping --echo-client 'test' --tcp --source-port [port] -v2 [Host 2 IP address]

For the `[port]` parameter, use the same port as the one specified when requesting the PCP mapping.

To terminate the test topology (along with the controller, the network application and the forwarder), simply terminate the script by pressing ctrl+C.

##Configuration

Several parameters of the network application can be configured in the `pcp_sdn_source/app_config.json` file, such as:
* minimum assigned lifetime for MAP and PEER mappings. For example, setting `default_pcp_map_assigned_lifetime_seconds` to 3600 causes the PCP server to assign mapping lifetime of at least 3600 seconds for MAP mappings (despite the fact that the PCP client may have requested a lower value). This is set to 0 by default, i.e. no minimum lifetime is defined. Deleting mappings still works properly if the client sends a PCP request with suggested lifetime set to 0 and the configuration has non-zero values for minimum lifetime.
* NAT pool, such as the range of internal IP addresses and ports to translate, and the range of external IP addresses and ports to use in translation.


#Known Issues, Limitations

* `read_command_output.sh` must be executed for all commands (`ryu-manager`, `ofprotocol` and `ofdatapath`), otherwise the execution the commands will be blocked. This issue stems from the fact that `pcp_sdn_test_topology.sh` writes to named pipes - the command that writes to a named pipe is blocked until a program reads from it.
* The current NAT implementation does not create implicit mappings. Mappings can only be created by sending PCP requests.
