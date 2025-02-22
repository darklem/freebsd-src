import ipaddress
import socket

import pytest
from atf_python.sys.net.netlink import NetlinkRtMessage
from atf_python.sys.net.netlink import NetlinkTestTemplate
from atf_python.sys.net.netlink import NlAttrIp
from atf_python.sys.net.netlink import NlConst
from atf_python.sys.net.netlink import NlmBaseFlags
from atf_python.sys.net.netlink import NlmGetFlags
from atf_python.sys.net.netlink import NlmNewFlags
from atf_python.sys.net.netlink import NlMsgType
from atf_python.sys.net.netlink import NlRtMsgType
from atf_python.sys.net.netlink import RtattrType
from atf_python.sys.net.vnet import SingleVnetTestTemplate


class TestRtNlRoute(NetlinkTestTemplate, SingleVnetTestTemplate):
    IPV6_PREFIXES = ["2001:db8::1/64"]

    def setup_method(self, method):
        super().setup_method(method)
        self.setup_netlink(NlConst.NETLINK_ROUTE)

    @pytest.mark.timeout(20)
    def test_buffer_override(self):
        msg_flags = (
            NlmBaseFlags.NLM_F_ACK.value
            | NlmBaseFlags.NLM_F_REQUEST.value
            | NlmNewFlags.NLM_F_CREATE.value
        )

        num_routes = 1000
        base_address = bytearray(ipaddress.ip_address("2001:db8:ffff::").packed)
        for i in range(num_routes):
            base_address[7] = i % 256
            base_address[6] = i // 256
            prefix_address = ipaddress.IPv6Address(bytes(base_address))

            msg = NetlinkRtMessage(self.helper, NlRtMsgType.RTM_NEWROUTE.value)
            msg.nl_hdr.nlmsg_flags = msg_flags
            msg.base_hdr.rtm_family = socket.AF_INET6
            msg.base_hdr.rtm_dst_len = 65
            msg.add_nla(NlAttrIp(RtattrType.RTA_DST, str(prefix_address)))
            msg.add_nla(NlAttrIp(RtattrType.RTA_GATEWAY, "2001:db8::2"))

            self.write_message(msg, silent=True)
            rx_msg = self.read_message(silent=True)
            assert rx_msg.is_type(NlMsgType.NLMSG_ERROR)
            assert msg.nl_hdr.nlmsg_seq == rx_msg.nl_hdr.nlmsg_seq
            assert rx_msg.error_code == 0
        # Now, dump
        msg = NetlinkRtMessage(self.helper, NlRtMsgType.RTM_GETROUTE.value)
        msg.nl_hdr.nlmsg_flags = (
            NlmBaseFlags.NLM_F_ACK.value
            | NlmBaseFlags.NLM_F_REQUEST.value
            | NlmGetFlags.NLM_F_ROOT.value
            | NlmGetFlags.NLM_F_MATCH.value
        )
        msg.base_hdr.rtm_family = socket.AF_INET6
        self.write_message(msg)
        num_received = 0
        while True:
            rx_msg = self.read_message(silent=True)
            if msg.nl_hdr.nlmsg_seq == rx_msg.nl_hdr.nlmsg_seq:
                if rx_msg.is_type(NlMsgType.NLMSG_ERROR):
                    if rx_msg.error_code != 0:
                        raise ValueError(
                            "unable to dump routes: error {}".format(rx_msg.error_code)
                        )
                if rx_msg.is_type(NlMsgType.NLMSG_DONE):
                    break
                if rx_msg.is_type(NlRtMsgType.RTM_NEWROUTE):
                    if rx_msg.base_hdr.rtm_dst_len == 65:
                        num_received += 1
        assert num_routes == num_received
